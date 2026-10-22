import re
import sys
from pathlib import Path
from random import Random

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fakes import FakeShopGateway, FakeTimer  # noqa: E402
from fakes_customers import FakeAccountPool, FakeAuthGateway, FakeJourney, FakeOrderGateway  # noqa: E402

from app.traffic.application.browse_shop import BrowseShop  # noqa: E402
from app.traffic.application.customer_session import CustomerSession  # noqa: E402
from app.traffic.application.journey_mix import JourneyMix  # noqa: E402
from app.traffic.application.new_customer_journey import NewCustomerJourney  # noqa: E402
from app.traffic.application.order_flow import OrderFlow  # noqa: E402
from app.traffic.application.returning_customer_journey import ReturningCustomerJourney  # noqa: E402
from app.traffic.application.token_parser import TokenParser  # noqa: E402
from app.traffic.domain.entities.product_ref import ProductRef  # noqa: E402
from app.traffic.domain.entities.traffic_report import TrafficReport  # noqa: E402
from app.traffic.domain.enums.payment_method import PaymentMethod  # noqa: E402
from app.traffic.domain.services.account_factory import AccountFactory  # noqa: E402
from app.traffic.domain.services.address_book import AddressBook  # noqa: E402
from app.traffic.domain.services.default_session_profiles import DEFAULT_SESSION_PROFILES  # noqa: E402
from app.traffic.domain.services.session_profile_picker import SessionProfilePicker  # noqa: E402
from app.traffic.domain.services.think_time_policy import ThinkTimePolicy  # noqa: E402
from app.traffic.domain.services.token_bucket import TokenBucket  # noqa: E402
from app.traffic.domain.value_objects.account import Account  # noqa: E402

PRODUCTS = [ProductRef(f"p{i}", f"slug-{i}") for i in range(1, 7)]
IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9_.-]{8,128}$")  # contrat de POST /orders


class Env:
    """Assemble les parcours avec des faux, sur un temps simulé."""

    def __init__(self, order_prob=1.0, decline_prob=0.0, typo_prob=0.0, auth=None, orders=None,
                 accounts=None, order_burst=4, auth_burst=20):
        self.timer = FakeTimer()
        self.think = ThinkTimePolicy(1.0)
        self.auth = auth or FakeAuthGateway()
        self.orders = orders or FakeOrderGateway()
        self.shop = FakeShopGateway()
        self.pool = FakeAccountPool(accounts)
        self.auth_limiter = TokenBucket(self.timer, 40, auth_burst)
        self.order_limiter = TokenBucket(self.timer, 8, order_burst)
        self.guest = BrowseShop(self.shop, self.timer, self.think, SessionProfilePicker(DEFAULT_SESSION_PROFILES))
        self.flow = OrderFlow(self.orders, self.timer, self.think, AddressBook(), self.order_limiter,
                              order_prob, decline_prob)
        self.session = CustomerSession(self.auth, self.orders, self.guest, self.flow)
        self.fallback = FakeJourney()
        self.new = NewCustomerJourney(self.auth, self.pool, self.auth_limiter, AccountFactory(), self.session,
                                      self.fallback, self.timer, self.think)
        self.returning = ReturningCustomerJourney(self.auth, self.pool, self.auth_limiter, self.session,
                                                  self.fallback, self.timer, self.think, typo_prob)
        self.report = TrafficReport()


def account(n: int = 1) -> Account:
    return Account(f"client-{n}@example.com", f"Bivouac-{n:020d}-Rando")


# --- OrderFlow ---------------------------------------------------------------------

def place(env: Env, seed: int = 1, token: str | None = "jeton-x") -> None:
    env.flow.place(PRODUCTS, "a@example.com", token, "cid-12345678", env.report, Random(seed))


def test_order_flow_creates_pays_and_confirms_in_order() -> None:
    env = Env()
    place(env)
    assert env.orders.names() == ["create_order", "request_payment", "confirm_payment"]
    assert env.orders.methods == [PaymentMethod.SUCCESS]
    assert dict(env.report.statuses) == {201: 2, 200: 1}


def test_order_is_valid_for_the_shop() -> None:
    env = Env()
    for seed in range(30):
        place(env, seed)
    assert env.orders.orders
    for order in env.orders.orders:
        assert 1 <= len(order.lines) <= 2 and all(line.quantity == 1 for line in order.lines)
        assert order.address.country in {"FR", "BE", "CH", "LU", "DE", "ES", "IT"}
    keys = env.orders.keys
    assert all(IDEMPOTENCY_KEY.match(key) for key in keys) and len(set(keys)) == len(keys)


def test_order_carries_the_customer_token() -> None:
    env = Env()
    place(env, token="jeton-abc")
    assert env.orders.tokens == ["jeton-abc"]


def test_order_probability_zero_never_orders() -> None:
    env = Env(order_prob=0.0)
    for seed in range(20):
        place(env, seed)
    assert env.orders.calls == []


def test_order_is_skipped_without_enough_rate_tokens() -> None:
    env = Env(order_burst=4)
    place(env, 1)   # consomme 3 jetons sur 4
    place(env, 2)   # il n'en reste qu'un (aucun temps écoulé) : il renonce
    assert env.orders.names().count("create_order") == 1


def test_orders_resume_when_the_bucket_refills() -> None:
    env = Env(order_burst=4)
    place(env, 1)
    env.timer.current += 120  # remplit le seau
    place(env, 2)
    assert env.orders.names().count("create_order") == 2


def test_a_failed_order_stops_before_payment() -> None:
    env = Env(orders=FakeOrderGateway(create_status=409))
    place(env)
    assert env.orders.names() == ["create_order"] and env.report.statuses[409] == 1


def test_a_failed_payment_request_skips_confirmation() -> None:
    env = Env(orders=FakeOrderGateway(pay_status=503))
    place(env)
    assert env.orders.names() == ["create_order", "request_payment"]


def test_declined_payment_can_be_retried_with_success() -> None:
    methods = set()
    for seed in range(40):
        env = Env(decline_prob=1.0, order_burst=5)   # 3 jetons pour la commande + 2 pour le réessai
        place(env, seed)
        methods.add(tuple(env.orders.methods))
    assert (PaymentMethod.DECLINED,) in methods
    assert (PaymentMethod.DECLINED, PaymentMethod.SUCCESS) in methods


def test_retry_after_decline_respects_the_rate_limit() -> None:
    env = Env(decline_prob=1.0, order_burst=3)   # 3 jetons : la commande les consomme tous, pas de réessai possible
    for seed in range(20):
        env.timer.current += 3600
        place(env, seed)
    assert PaymentMethod.SUCCESS not in env.orders.methods


def test_no_products_means_no_order() -> None:
    env = Env()
    env.flow.place([], "a@example.com", None, "cid-12345678", env.report, Random(1))
    assert env.orders.calls == []


@pytest.mark.parametrize("kwargs", [{"order_prob": 1.2}, {"decline_prob": -0.1}])
def test_order_flow_rejects_invalid_probabilities(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        Env(**kwargs)


# --- NewCustomerJourney ------------------------------------------------------------

def test_new_customer_registers_logs_in_then_shops() -> None:
    env = Env()
    env.new.execute(env.report, Random(1))
    names = env.auth.names()
    assert names[:3] == ["register", "login", "me"]
    assert env.report.sessions == 1
    assert env.orders.tokens and all(t and t.startswith("jeton-client-") for t in env.orders.tokens)


def test_new_customer_account_joins_the_pool_afterwards() -> None:
    env = Env()
    env.new.execute(env.report, Random(1))
    assert len(env.pool.available) == 1 and env.pool.available[0].email == env.orders.orders[0].email


def test_failed_registration_stops_there_and_adds_no_account() -> None:
    env = Env(auth=FakeAuthGateway(register_status=422))
    env.new.execute(env.report, Random(1))
    assert env.auth.names() == ["register"]
    assert env.pool.available == [] and env.report.sessions == 1


def test_new_customer_falls_back_to_a_guest_when_the_auth_bucket_is_empty() -> None:
    env = Env(auth_burst=2)
    env.auth_limiter.try_acquire(2)            # seau vide
    env.new.execute(env.report, Random(1))
    assert env.fallback.runs == 1 and env.auth.calls == []


# --- ReturningCustomerJourney ------------------------------------------------------

def test_returning_customer_without_account_falls_back() -> None:
    env = Env()
    env.returning.execute(env.report, Random(1))
    assert env.fallback.runs == 1 and env.auth.calls == []


def test_returning_customer_logs_in_with_the_right_password() -> None:
    known = account()
    env = Env(accounts=[known], auth=FakeAuthGateway())
    env.auth.passwords[known.email] = known.password
    env.returning.execute(env.report, Random(1))
    assert env.auth.names()[:2] == ["login", "me"] and env.auth.failed_logins == 0
    assert env.pool.released == [known]


def test_typo_gives_exactly_one_failure_followed_by_a_success() -> None:
    known = account()
    env = Env(accounts=[known], typo_prob=1.0)
    env.auth.passwords[known.email] = known.password
    env.returning.execute(env.report, Random(1))
    assert env.auth.names()[:3] == ["login", "login", "me"]
    assert env.auth.failed_logins == 1 and env.report.statuses[401] == 1


def test_lockout_threshold_is_never_approached() -> None:
    """Le verrouillage d'auth tombe à 5 échecs d'affilée : jamais plus d'un échec avant une connexion réussie."""
    known = account()
    env = Env(accounts=[known], typo_prob=1.0)
    env.auth.passwords[known.email] = known.password
    consecutive, worst = 0, 0
    for seed in range(60):
        env.timer.current += 600
        before = env.auth.failed_logins
        env.returning.execute(env.report, Random(seed))
        consecutive = consecutive + 1 if env.auth.calls[-1][0] != "me" and env.auth.failed_logins > before else 0
        worst = max(worst, consecutive)
    assert env.auth.failed_logins == 60 and worst <= 1
    assert [name for name in env.auth.names() if name == "login"].count("login") == 120


def test_account_is_released_even_if_the_visit_crashes() -> None:
    known = account()
    env = Env(accounts=[known])
    env.auth.passwords[known.email] = known.password

    def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    env.session.run = boom
    with pytest.raises(RuntimeError):
        env.returning.execute(env.report, Random(1))
    assert env.pool.released == [known]


def test_returning_customer_gives_the_account_back_and_falls_back_without_tokens() -> None:
    known = account()
    env = Env(accounts=[known], auth_burst=2, typo_prob=1.0)
    env.auth_limiter.try_acquire(2)             # seau vide
    env.returning.execute(env.report, Random(1))
    assert env.fallback.runs == 1 and env.pool.released == [known] and env.auth.calls == []


def test_returning_customer_rejects_an_invalid_typo_probability() -> None:
    with pytest.raises(ValueError):
        Env(typo_prob=2.0)


def test_failed_login_after_a_typo_does_not_shop() -> None:
    known = account()
    env = Env(accounts=[known], typo_prob=1.0)   # compte inconnu d'auth : les deux connexions échouent
    env.returning.execute(env.report, Random(1))
    assert "me" not in env.auth.names() and env.orders.calls == []


# --- CustomerSession, JourneyMix, TokenParser ---------------------------------------

def test_customer_session_reads_profile_browses_orders_and_may_list_orders() -> None:
    env = Env()
    names = set()
    for seed in range(20):
        env.timer.current += 3600
        env.session.run("a@example.com", "jeton-a", "cid-12345678", env.report, Random(seed))
        names |= set(env.orders.names())
    assert env.auth.names().count("me") == 20
    assert {"create_order", "my_orders"} <= names


def test_journey_mix_follows_the_weights() -> None:
    first, second = FakeJourney(), FakeJourney()
    mix, rng, report = JourneyMix([(1, first), (3, second)]), Random(4), TrafficReport()
    for _ in range(2000):
        mix.execute(report, rng)
    assert first.runs + second.runs == 2000 and second.runs > 2 * first.runs


@pytest.mark.parametrize("journeys", [[], [(0, FakeJourney())], [(-1, FakeJourney())]])
def test_journey_mix_needs_positive_weights(journeys) -> None:
    with pytest.raises(ValueError):
        JourneyMix(journeys)


def test_token_parser() -> None:
    parser = TokenParser()
    assert parser.access_token({"access_token": "abc"}) == "abc"
    assert parser.access_token({"access_token": ""}) is None and parser.access_token(None) is None
    assert parser.access_token({"access_token": 3}) is None
    assert parser.order_id({"id": "o-1"}) == "o-1" and parser.order_id({}) is None
