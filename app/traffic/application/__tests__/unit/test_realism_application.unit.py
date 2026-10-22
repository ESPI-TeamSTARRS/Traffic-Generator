import sys
from collections import Counter
from pathlib import Path
from random import Random

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fakes import FakeShopGateway, FakeTimer  # noqa: E402
from fakes_customers import FakeAccountPool, FakeAuthGateway, FakeJourney, FakeOrderGateway  # noqa: E402

from app.traffic.application.browse_shop import UNKNOWN_PRODUCT_ID, BrowseShop  # noqa: E402
from app.traffic.application.customer_session import CustomerSession  # noqa: E402
from app.traffic.application.new_customer_journey import NewCustomerJourney  # noqa: E402
from app.traffic.application.order_flow import OrderFlow  # noqa: E402
from app.traffic.application.returning_customer_journey import ReturningCustomerJourney  # noqa: E402
from app.traffic.domain.entities.product_ref import ProductRef  # noqa: E402
from app.traffic.domain.entities.traffic_report import TrafficReport  # noqa: E402
from app.traffic.domain.enums.payment_method import PaymentMethod  # noqa: E402
from app.traffic.domain.services.account_factory import AccountFactory  # noqa: E402
from app.traffic.domain.services.address_book import AddressBook  # noqa: E402
from app.traffic.domain.services.default_session_profiles import DEFAULT_SESSION_PROFILES  # noqa: E402
from app.traffic.domain.services.popularity_policy import PopularityPolicy  # noqa: E402
from app.traffic.domain.services.session_profile_picker import SessionProfilePicker  # noqa: E402
from app.traffic.domain.services.think_time_policy import ThinkTimePolicy  # noqa: E402
from app.traffic.domain.services.token_bucket import TokenBucket  # noqa: E402
from app.traffic.domain.value_objects.account import Account  # noqa: E402

PRODUCTS = [ProductRef(f"p{i}", f"slug-{i}") for i in range(1, 7)]


def browse(slip: float = 0.0, seed: int = 1, popularity=None) -> tuple[FakeShopGateway, TrafficReport]:
    gateway, report = FakeShopGateway(), TrafficReport()
    BrowseShop(gateway, FakeTimer(), ThinkTimePolicy(1.0), SessionProfilePicker(DEFAULT_SESSION_PROFILES),
               popularity=popularity, slip_probability=slip).execute(report, Random(seed))
    return gateway, report


# --- Gestes maladroits dans la navigation -------------------------------------------------

def test_without_slips_no_invalid_query_is_ever_sent() -> None:
    for seed in range(40):
        gateway, _ = browse(slip=0.0, seed=seed)
        assert "list_bad_query" not in gateway.names()
        for name, lines in gateway.calls:
            if name == "quote_cart":
                assert len({line.product_id for line in lines}) == len(lines)


def test_slips_send_invalid_listings_and_invalid_quotes() -> None:
    bad_listings, duplicates, unknown = 0, 0, 0
    for seed in range(80):
        gateway, _ = browse(slip=1.0, seed=seed)
        bad_listings += gateway.names().count("list_bad_query")
        for name, lines in gateway.calls:
            if name == "quote_cart":
                duplicates += len({line.product_id for line in lines}) < len(lines)
                unknown += any(line.product_id == UNKNOWN_PRODUCT_ID for line in lines)
    assert bad_listings > 10 and duplicates > 5 and unknown > 5


def test_bad_query_refusal_is_counted() -> None:
    counted = sum(browse(slip=1.0, seed=seed)[1].statuses[422] for seed in range(30))
    assert counted > 10


def test_popularity_skews_the_viewed_products() -> None:
    views: Counter[str] = Counter()
    for seed in range(300):
        gateway, _ = browse(popularity=PopularityPolicy(), seed=seed)
        views.update(arg for name, arg in gateway.calls if name == "get_product")
    assert views["tente-a"] > 2 * views["gourde-f"]     # p1 est le mieux classé du catalogue de test, p6 le moins


def test_browse_shop_rejects_an_invalid_slip_probability() -> None:
    with pytest.raises(ValueError):
        BrowseShop(FakeShopGateway(), FakeTimer(), ThinkTimePolicy(1.0), SessionProfilePicker(DEFAULT_SESSION_PROFILES),
                   slip_probability=1.5)


# --- Commande : abandons, rejeux, suivi ----------------------------------------------------

def order_flow(orders: FakeOrderGateway, abandon=0.0, slip=0.0, decline=0.0) -> tuple[OrderFlow, TrafficReport]:
    timer = FakeTimer()
    flow = OrderFlow(orders, timer, ThinkTimePolicy(1.0), AddressBook(), TokenBucket(timer, 600, 50), 1.0, decline,
                     abandon_probability=abandon, slip_probability=slip)
    return flow, TrafficReport()


def place(flow: OrderFlow, report: TrafficReport, seed: int = 1) -> None:
    flow.place(PRODUCTS, "a@example.com", "jeton-x", "cid-12345678", report, Random(seed))


def test_abandon_probability_one_leaves_every_order_unpaid() -> None:
    orders = FakeOrderGateway()
    flow, report = order_flow(orders, abandon=1.0)
    for seed in range(10):
        place(flow, report, seed)
    assert orders.names().count("create_order") == 10 and "request_payment" not in orders.names()


def test_abandon_on_the_payment_page_requests_without_confirming() -> None:
    requested_only = 0
    for seed in range(200):
        orders = FakeOrderGateway()
        flow, report = order_flow(orders, abandon=0.6)
        place(flow, report, seed)
        names = orders.names()
        requested_only += "request_payment" in names and "confirm_payment" not in names
    assert requested_only > 10


def test_no_abandon_means_every_order_is_paid() -> None:
    orders = FakeOrderGateway()
    flow, report = order_flow(orders, abandon=0.0)
    for seed in range(10):
        place(flow, report, seed)
    assert orders.names().count("confirm_payment") == 10


def test_double_click_replays_the_same_idempotency_key() -> None:
    orders = FakeOrderGateway()
    flow, report = order_flow(orders, slip=1.0)
    place(flow, report)
    assert orders.names().count("create_order") == 2 and orders.keys[0] == orders.keys[1]


def test_double_confirmation_follows_a_successful_payment() -> None:
    orders = FakeOrderGateway()
    flow, report = order_flow(orders, slip=1.0)
    place(flow, report)
    assert orders.names().count("confirm_payment") == 2 and orders.methods == [PaymentMethod.SUCCESS] * 2


def test_declined_payment_is_not_double_confirmed() -> None:
    orders = FakeOrderGateway()
    flow, report = order_flow(orders, slip=1.0, decline=1.0)
    place(flow, report)
    assert orders.methods[0] is PaymentMethod.DECLINED and orders.methods.count(PaymentMethod.SUCCESS) <= 1


def test_tracking_sometimes_uses_a_wrong_email() -> None:
    right, wrong = 0, 0
    for seed in range(300):
        orders = FakeOrderGateway()
        flow, report = order_flow(orders, slip=0.5)
        place(flow, report, seed)
        for name, email in orders.calls:
            if name == "lookup_order":
                right += email == "a@example.com"
                wrong += email != "a@example.com"
    assert right > 5 and wrong > 2


def test_tracking_uses_the_right_email_when_there_are_no_slips() -> None:
    for seed in range(100):
        orders = FakeOrderGateway()
        flow, report = order_flow(orders, slip=0.0)
        place(flow, report, seed)
        assert all(email == "a@example.com" for name, email in orders.calls if name == "lookup_order")


def test_extra_actions_respect_the_rate_limit() -> None:
    orders = FakeOrderGateway()
    timer = FakeTimer()
    flow = OrderFlow(orders, timer, ThinkTimePolicy(1.0), AddressBook(), TokenBucket(timer, 6, 3), 1.0, 0.0,
                     slip_probability=1.0)
    place(flow, TrafficReport())             # 3 jetons pour la commande : plus rien pour le rejeu ni le suivi
    assert orders.names().count("create_order") == 1 and "lookup_order" not in orders.names()


def test_order_flow_rejects_invalid_realism_probabilities() -> None:
    timer = FakeTimer()
    for kwargs in ({"abandon_probability": 2.0}, {"slip_probability": -1.0}):
        with pytest.raises(ValueError):
            OrderFlow(FakeOrderGateway(), timer, ThinkTimePolicy(1.0), AddressBook(), TokenBucket(timer, 6, 3), 1.0,
                      0.0, **kwargs)


# --- Inscription et connexion : erreurs de saisie -------------------------------------------

class Env:
    def __init__(self, slip: float = 0.0, typo: float = 0.0, unknown: float = 0.0, accounts=None) -> None:
        self.timer = FakeTimer()
        self.think = ThinkTimePolicy(1.0)
        self.auth, self.orders, self.pool = FakeAuthGateway(), FakeOrderGateway(), FakeAccountPool(accounts)
        guest = BrowseShop(FakeShopGateway(), self.timer, self.think, SessionProfilePicker(DEFAULT_SESSION_PROFILES))
        flow = OrderFlow(self.orders, self.timer, self.think, AddressBook(), TokenBucket(self.timer, 600, 50), 0.0, 0.0)
        session = CustomerSession(self.auth, self.orders, guest, flow)
        limiter = TokenBucket(self.timer, 600, 50)
        self.fallback = FakeJourney()
        self.new = NewCustomerJourney(self.auth, self.pool, limiter, AccountFactory(), session, self.fallback,
                                      self.timer, self.think, slip_probability=slip)
        self.returning = ReturningCustomerJourney(self.auth, self.pool, limiter, session, self.fallback, self.timer,
                                                  self.think, typo, unknown)
        self.report = TrafficReport()


def test_registration_slips_end_with_a_valid_account() -> None:
    refused, duplicated, created = 0, 0, 0
    for seed in range(120):
        env = Env(slip=1.0)
        env.new.execute(env.report, Random(seed))
        registers = [email for name, email in env.auth.calls if name == "register"]
        refused += env.report.statuses[422] > 0
        duplicated += len(registers) == 2 and registers[0] == registers[1]
        created += bool(env.pool.available)
        assert env.auth.names().count("login") <= 1
    assert refused > 20 and duplicated > 20 and created == 120


def test_flawed_registration_precedes_the_correct_one_with_a_different_account() -> None:
    for seed in range(40):
        env = Env(slip=1.0)
        env.new.execute(env.report, Random(seed))
        registers = [email for name, email in env.auth.calls if name == "register"]
        if env.report.statuses[422]:
            assert len(registers) == 2
            assert env.pool.available[0].email == registers[1]


def test_no_registration_slip_without_probability() -> None:
    for seed in range(40):
        env = Env(slip=0.0)
        env.new.execute(env.report, Random(seed))
        assert env.auth.names().count("register") == 1 and env.report.statuses[422] == 0


def test_unknown_email_failure_uses_a_fresh_address_each_time() -> None:
    known = Account("client-1@example.com", "Bivouac-00000000000000000001-Rando")
    attempted: list[str] = []
    for seed in range(50):
        env = Env(unknown=1.0, accounts=[known])
        env.auth.passwords[known.email] = known.password
        env.returning.execute(env.report, Random(seed))
        logins = [email for name, email in env.auth.calls if name == "login"]
        assert logins[-1] == known.email and len(logins) == 2 and env.auth.failed_logins == 1
        attempted.append(logins[0])
    assert len(set(attempted)) == 50 and known.email not in attempted


def test_at_most_one_failed_login_per_visit_even_with_both_mistakes_enabled() -> None:
    known = Account("client-1@example.com", "Bivouac-00000000000000000001-Rando")
    for seed in range(60):
        env = Env(typo=1.0, unknown=1.0, accounts=[known])
        env.auth.passwords[known.email] = known.password
        env.returning.execute(env.report, Random(seed))
        assert env.auth.failed_logins == 1


def test_returning_customer_rejects_an_invalid_unknown_email_probability() -> None:
    with pytest.raises(ValueError):
        Env(unknown=2.0)


def test_new_customer_rejects_an_invalid_slip_probability() -> None:
    with pytest.raises(ValueError):
        Env(slip=-0.1)
