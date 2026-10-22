import re
from random import Random

import pytest

from app.traffic.domain.enums.payment_method import PaymentMethod
from app.traffic.domain.services.account_factory import AccountFactory
from app.traffic.domain.services.address_book import AddressBook
from app.traffic.domain.services.correlation_id_factory import CorrelationIdFactory
from app.traffic.domain.services.token_bucket import TokenBucket
from app.traffic.domain.value_objects.account import Account
from app.traffic.domain.value_objects.cart_line import CartLine
from app.traffic.domain.value_objects.order_request import OrderRequest
from app.traffic.domain.value_objects.shipping_address import ShippingAddress

ADDRESS = ShippingAddress("Camille Martin", "12 rue des Alpes", "38000", "Grenoble", "FR")
COUNTRIES = {"FR", "BE", "CH", "LU", "DE", "ES", "IT"}  # liste acceptée par le shop


class ClockStub:
    def __init__(self) -> None:
        self.current = 0.0

    def now(self) -> float:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.current += seconds


# --- TokenBucket ------------------------------------------------------------------

def test_bucket_starts_full_and_refuses_beyond_the_burst() -> None:
    bucket = TokenBucket(ClockStub(), per_minute=6, burst=3)
    assert [bucket.try_acquire() for _ in range(4)] == [True, True, True, False]


def test_bucket_refills_with_time_up_to_the_burst() -> None:
    clock = ClockStub()
    bucket = TokenBucket(clock, per_minute=6, burst=3)  # 1 jeton toutes les 10 s
    for _ in range(3):
        bucket.try_acquire()
    clock.current = 10
    assert bucket.try_acquire() is True and bucket.try_acquire() is False
    clock.current = 10_000  # très longtemps : plafonné à la rafale
    assert [bucket.try_acquire() for _ in range(4)] == [True, True, True, False]


def test_bucket_cost_takes_several_tokens_at_once_or_none() -> None:
    bucket = TokenBucket(ClockStub(), per_minute=6, burst=4)
    assert bucket.try_acquire(3) is True
    assert bucket.try_acquire(3) is False       # il n'en reste qu'un : rien n'est consommé
    assert bucket.try_acquire(1) is True


@pytest.mark.parametrize("kwargs", [{"per_minute": 0, "burst": 3}, {"per_minute": 5, "burst": 0}])
def test_bucket_rejects_invalid_configuration(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        TokenBucket(ClockStub(), **kwargs)


@pytest.mark.parametrize("cost", [0, 5])
def test_bucket_rejects_a_cost_outside_the_burst(cost: int) -> None:
    with pytest.raises(ValueError):
        TokenBucket(ClockStub(), per_minute=6, burst=4).try_acquire(cost)


# --- Comptes et commandes ----------------------------------------------------------

def test_account_factory_makes_unique_valid_credentials() -> None:
    rng, factory = Random(1), AccountFactory()
    accounts = [factory.create(rng) for _ in range(500)]
    assert len({a.email for a in accounts}) == 500
    assert all(re.fullmatch(r"client-[0-9a-f]{12}@example\.com", a.email) for a in accounts)
    assert all(12 <= len(a.password) <= 128 for a in accounts)  # politique d'auth : 12 à 128 caractères


def test_account_factory_is_reproducible() -> None:
    assert AccountFactory().create(Random(7)) == AccountFactory().create(Random(7))


def test_mistyped_account_keeps_the_email_and_breaks_the_password() -> None:
    account = Account("a@example.com", "motdepasse-long-1")
    typo = account.mistyped()
    assert typo.email == account.email and typo.password != account.password


def test_order_request_needs_lines_without_duplicates() -> None:
    assert OrderRequest("a@example.com", ADDRESS, (CartLine("p1", 1),)).lines
    with pytest.raises(ValueError):
        OrderRequest("a@example.com", ADDRESS, ())
    with pytest.raises(ValueError):
        OrderRequest("a@example.com", ADDRESS, (CartLine("p1", 1), CartLine("p1", 2)))


def test_address_book_only_uses_countries_the_shop_accepts() -> None:
    book, rng = AddressBook(), Random(2)
    assert {book.pick(rng).country for _ in range(200)} <= COUNTRIES


def test_address_book_needs_an_address() -> None:
    with pytest.raises(ValueError):
        AddressBook(())


def test_correlation_id_matches_the_basecamp_middleware_format() -> None:
    value = CorrelationIdFactory().create(Random(3))
    assert re.fullmatch(r"[A-Za-z0-9-]{8,64}", value)
    assert CorrelationIdFactory().create(Random(3)) == value


def test_payment_methods_are_the_shop_test_methods() -> None:
    assert {m.value for m in PaymentMethod} == {"pm_test_success", "pm_test_declined"}
