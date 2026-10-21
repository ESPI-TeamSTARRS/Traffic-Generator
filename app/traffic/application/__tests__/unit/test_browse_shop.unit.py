import re
import sys
from pathlib import Path
from random import Random

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fakes import FakeShopGateway, FakeTimer  # noqa: E402

from app.traffic.application.browse_shop import BrowseShop  # noqa: E402
from app.traffic.domain.entities.shop_response import ShopResponse  # noqa: E402
from app.traffic.domain.entities.traffic_report import TrafficReport  # noqa: E402
from app.traffic.domain.services.think_time_policy import ThinkTimePolicy  # noqa: E402
from app.traffic.domain.value_objects.cart_line import CartLine  # noqa: E402

CORRELATION_PATTERN = re.compile(r"^[A-Za-z0-9-]{8,64}$")  # contrat du middleware Basecamp


def run_session(gateway: FakeShopGateway, seed: int) -> tuple[TrafficReport, FakeTimer]:
    timer, report = FakeTimer(), TrafficReport()
    BrowseShop(gateway, timer, ThinkTimePolicy(2.0), Random(seed)).execute(report)
    return report, timer


def test_session_starts_by_listing_the_catalog_and_counts_one_session() -> None:
    gateway = FakeShopGateway()
    report, _ = run_session(gateway, seed=1)
    assert gateway.names()[0] == "list_products"
    assert report.sessions == 1
    assert report.requests == len(gateway.calls)


def test_viewed_products_come_from_the_catalog() -> None:
    gateway = FakeShopGateway()
    run_session(gateway, seed=1)
    viewed = {arg for name, arg in gateway.calls if name == "get_product"}
    assert viewed and viewed <= {"tente-a", "sac-b", "duvet-c"}


@pytest.mark.parametrize("seed", range(20))
def test_quotes_are_valid_for_the_shop(seed: int) -> None:
    gateway = FakeShopGateway()
    run_session(gateway, seed)
    for name, lines in gateway.calls:
        if name == "quote_cart":
            assert 1 <= len(lines) <= 3
            assert all(isinstance(line, CartLine) and line.product_id in {"p1", "p2", "p3"} for line in lines)
            assert len({line.product_id for line in lines}) == len(lines)  # pas de doublon (rejeté par le shop)


def test_one_correlation_id_per_session_respecting_the_basecamp_format() -> None:
    gateway = FakeShopGateway()
    run_session(gateway, seed=3)
    assert len(set(gateway.correlation_ids)) == 1
    assert CORRELATION_PATTERN.match(gateway.correlation_ids[0])


def test_session_with_failing_catalog_does_not_view_or_quote() -> None:
    gateway = FakeShopGateway(catalog=ShopResponse(503))
    report, _ = run_session(gateway, seed=1)
    assert set(gateway.names()) <= {"list_products", "health"}
    assert report.statuses[503] == 1


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
