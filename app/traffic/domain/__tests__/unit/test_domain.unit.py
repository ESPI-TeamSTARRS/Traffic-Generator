from random import Random

import pytest

from app.traffic.domain.entities.shop_response import ShopResponse
from app.traffic.domain.entities.traffic_report import TrafficReport
from app.traffic.domain.services.default_session_profiles import DEFAULT_SESSION_PROFILES
from app.traffic.domain.services.load_profile import LoadProfile
from app.traffic.domain.services.session_profile_picker import SessionProfilePicker
from app.traffic.domain.services.think_time_policy import ThinkTimePolicy
from app.traffic.domain.value_objects.cart_line import CartLine
from app.traffic.domain.value_objects.session_profile import SessionProfile


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


@pytest.mark.parametrize(
    "kwargs",
    [
        {"weight": 0}, {"listings": 0}, {"min_views": 3, "max_views": 2}, {"min_views": -1},
        {"quote_probability": 1.2}, {"quote_probability": -0.1},
    ],
)
def test_session_profile_rejects_invalid_values(kwargs: dict) -> None:
    base = {"name": "x", "weight": 1, "listings": 1, "min_views": 0, "max_views": 1, "quote_probability": 0.5}
    with pytest.raises(ValueError):
        SessionProfile(**{**base, **kwargs})


def test_picker_follows_weights_and_covers_every_default_profile() -> None:
    picker, rng = SessionProfilePicker(DEFAULT_SESSION_PROFILES), Random(3)
    picks = [picker.pick(rng).name for _ in range(4000)]
    assert set(picks) == {profile.name for profile in DEFAULT_SESSION_PROFILES}
    assert picks.count("flaneur") > picks.count("explorateur") * 2


def test_picker_requires_a_profile() -> None:
    with pytest.raises(ValueError):
        SessionProfilePicker([])


def test_constant_load_without_a_day() -> None:
    assert LoadProfile().factor(123.0) == 1.0


def test_load_goes_from_night_to_peak_and_back() -> None:
    load = LoadProfile(day_length_seconds=600, night_factor=0.2)
    assert load.factor(0) == pytest.approx(0.2)
    assert load.factor(300) == pytest.approx(1.0)
    assert load.factor(600) == pytest.approx(0.2)


@pytest.mark.parametrize("kwargs", [{"day_length_seconds": 0}, {"night_factor": 0}, {"night_factor": 1.5}])
def test_load_profile_rejects_invalid_values(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        LoadProfile(**kwargs)
