from random import Random

import pytest

from app.traffic.domain.entities.shop_response import ShopResponse
from app.traffic.domain.entities.traffic_report import TrafficReport
from app.traffic.domain.services.think_time_policy import ThinkTimePolicy
from app.traffic.domain.value_objects.cart_line import CartLine


@pytest.mark.parametrize("quantity", [0, 11, -1])
def test_cart_line_rejects_quantity_the_shop_would_refuse(quantity: int) -> None:
    with pytest.raises(ValueError):
        CartLine("p1", quantity)


def test_cart_line_accepts_bounds() -> None:
    assert CartLine("p1", 1).quantity == 1
    assert CartLine("p1", 10).quantity == 10


def test_report_counts_requests_per_status() -> None:
    report = TrafficReport()
    for status in (200, 200, 404):
        report.record(status)
    report.end_session()
    assert (report.sessions, report.requests, report.statuses[200]) == (1, 3, 2)


@pytest.mark.parametrize("status, expected", [(200, True), (299, True), (404, False), (0, False)])
def test_response_success(status: int, expected: bool) -> None:
    assert ShopResponse(status).is_success is expected


def test_think_time_is_positive_with_expected_mean() -> None:
    rng, policy = Random(7), ThinkTimePolicy(2.0)
    samples = [policy.sample(rng) for _ in range(5000)]
    assert min(samples) >= 0
    assert sum(samples) / len(samples) == pytest.approx(2.0, rel=0.1)


def test_think_time_requires_positive_mean() -> None:
    with pytest.raises(ValueError):
        ThinkTimePolicy(0)
