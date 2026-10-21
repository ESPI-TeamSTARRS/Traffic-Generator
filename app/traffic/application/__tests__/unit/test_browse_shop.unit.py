import re
import sys
from pathlib import Path
from random import Random

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fakes import FakeShopGateway, FakeTimer  # noqa: E402

from app.traffic.application.browse_shop import UNKNOWN_SLUG, BrowseShop  # noqa: E402
from app.traffic.domain.entities.shop_response import ShopResponse  # noqa: E402
from app.traffic.domain.entities.traffic_report import TrafficReport  # noqa: E402
from app.traffic.domain.services.default_session_profiles import DEFAULT_SESSION_PROFILES  # noqa: E402
from app.traffic.domain.services.session_profile_picker import SessionProfilePicker  # noqa: E402
from app.traffic.domain.services.think_time_policy import ThinkTimePolicy  # noqa: E402
from app.traffic.domain.value_objects.cart_line import CartLine  # noqa: E402
from app.traffic.domain.value_objects.session_profile import SessionProfile  # noqa: E402

CORRELATION_PATTERN = re.compile(r"^[A-Za-z0-9-]{8,64}$")  # contrat du middleware Basecamp
KNOWN_IDS = {"p1", "p2", "p3", "p4", "p5", "p6"}


def run_session(
    gateway: FakeShopGateway, seed: int, refusal: float = 0.0, profiles=DEFAULT_SESSION_PROFILES
) -> tuple[TrafficReport, FakeTimer]:
    timer, report = FakeTimer(), TrafficReport()
    browse = BrowseShop(gateway, timer, ThinkTimePolicy(2.0), SessionProfilePicker(profiles), refusal)
    browse.execute(report, Random(seed))
    return report, timer


def test_session_starts_by_listing_the_catalog_and_counts_one_session() -> None:
    gateway = FakeShopGateway()
    report, _ = run_session(gateway, seed=1)
    assert gateway.names()[0] == "list_products"
    assert report.sessions == 1
    assert report.requests == len(gateway.calls)


@pytest.mark.parametrize("seed", range(20))
def test_viewed_products_and_quotes_come_from_the_catalog_and_are_valid(seed: int) -> None:
    gateway = FakeShopGateway()
    run_session(gateway, seed)
    for name, argument in gateway.calls:
        if name == "get_product":
            assert argument in {"tente-a", "sac-b", "duvet-c", "rechaud-d", "frontale-e", "gourde-f"}
        if name == "quote_cart":
            assert 1 <= len(argument) <= 3
            assert all(isinstance(line, CartLine) and line.product_id in KNOWN_IDS for line in argument)
            assert len({line.product_id for line in argument}) == len(argument)  # un doublon serait refusé par le shop


def test_sessions_differ_in_length() -> None:
    lengths = set()
    for seed in range(60):
        gateway = FakeShopGateway()
        run_session(gateway, seed)
        lengths.add(len(gateway.calls))
    assert len(lengths) >= 5 and min(lengths) <= 2 and max(lengths) >= 7


def test_curious_visitor_loads_two_pages_and_leaves() -> None:
    curious = SessionProfile("curieux", 1, listings=1, min_views=1, max_views=1, quote_probability=0)
    gateway = FakeShopGateway()
    run_session(gateway, seed=1, profiles=[curious])
    assert gateway.names()[:2] == ["list_products", "get_product"]
    assert "quote_cart" not in gateway.names()


def test_explorer_lists_several_times() -> None:
    explorer = SessionProfile("explorateur", 1, listings=3, min_views=0, max_views=0, quote_probability=0)
    gateway = FakeShopGateway()
    run_session(gateway, seed=1, profiles=[explorer])
    assert gateway.names().count("list_products") == 3


def test_one_correlation_id_per_session_respecting_the_basecamp_format() -> None:
    gateway = FakeShopGateway()
    run_session(gateway, seed=3)
    assert len(set(gateway.correlation_ids)) == 1
    assert CORRELATION_PATTERN.match(gateway.correlation_ids[0])


def test_session_with_failing_catalog_does_not_view_or_quote() -> None:
    gateway = FakeShopGateway(catalog=ShopResponse(503))
    report, _ = run_session(gateway, seed=1)
    assert set(gateway.names()) <= {"list_products", "health"}
    assert report.statuses[503] >= 1


def test_session_with_empty_catalog_body_is_harmless() -> None:
    gateway = FakeShopGateway(catalog=ShopResponse(200, {"items": []}))
    report, _ = run_session(gateway, seed=1)
    assert "get_product" not in gateway.names()
    assert report.sessions == 1


def test_visitor_thinks_between_actions() -> None:
    gateway = FakeShopGateway()
    _, timer = run_session(gateway, seed=1)
    assert timer.sleeps and all(pause >= 0 for pause in timer.sleeps)


def test_same_seed_gives_same_traffic() -> None:
    first, second = FakeShopGateway(), FakeShopGateway()
    run_session(first, seed=42)
    run_session(second, seed=42)
    assert first.calls == second.calls


def test_refusal_rate_one_always_asks_for_an_unknown_product() -> None:
    gateway = FakeShopGateway()
    report, _ = run_session(gateway, seed=1, refusal=1.0)
    assert ("get_product", UNKNOWN_SLUG) in gateway.calls
    assert report.statuses[404] == 1


def test_refusal_rate_zero_never_does() -> None:
    for seed in range(30):
        gateway = FakeShopGateway()
        report, _ = run_session(gateway, seed, refusal=0.0)
        assert report.statuses[404] == 0


def test_rejects_invalid_refusal_probability() -> None:
    with pytest.raises(ValueError):
        picker = SessionProfilePicker(DEFAULT_SESSION_PROFILES)
        BrowseShop(FakeShopGateway(), FakeTimer(), ThinkTimePolicy(1), picker, 1.5)
