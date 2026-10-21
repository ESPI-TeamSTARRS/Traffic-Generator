import sys
from pathlib import Path
from random import Random

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fakes import FakeShopGateway, FakeTimer  # noqa: E402

from app.traffic.application.browse_shop import BrowseShop  # noqa: E402
from app.traffic.application.run_traffic import RunTraffic  # noqa: E402
from app.traffic.domain.services.think_time_policy import ThinkTimePolicy  # noqa: E402


def build(gateway: FakeShopGateway, timer: FakeTimer, seed: int = 1) -> RunTraffic:
    rng = Random(seed)
    return RunTraffic(BrowseShop(gateway, timer, ThinkTimePolicy(1.0), rng), timer, rng)


def test_runs_sessions_until_the_deadline() -> None:
    timer = FakeTimer()
    report = build(FakeShopGateway(), timer).execute(duration_seconds=300, sessions_per_minute=6)
    assert report.sessions > 1
    assert timer.current >= 300


def test_higher_rate_produces_more_sessions() -> None:
    slow = build(FakeShopGateway(), FakeTimer()).execute(600, sessions_per_minute=2)
    fast = build(FakeShopGateway(), FakeTimer()).execute(600, sessions_per_minute=20)
    assert fast.sessions > slow.sessions


@pytest.mark.parametrize("duration, rate", [(0, 6), (-1, 6), (60, 0), (60, -2)])
def test_rejects_non_positive_parameters(duration: float, rate: float) -> None:
    with pytest.raises(ValueError):
        build(FakeShopGateway(), FakeTimer()).execute(duration, rate)
