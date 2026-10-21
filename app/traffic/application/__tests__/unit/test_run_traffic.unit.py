import sys
from pathlib import Path
from random import Random

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fakes import FakeShopGateway, FakeTimer, InlineSpawner  # noqa: E402

from app.traffic.application.browse_shop import BrowseShop  # noqa: E402
from app.traffic.application.run_traffic import RunTraffic  # noqa: E402
from app.traffic.domain.services.default_session_profiles import DEFAULT_SESSION_PROFILES  # noqa: E402
from app.traffic.domain.services.load_profile import LoadProfile  # noqa: E402
from app.traffic.domain.services.session_profile_picker import SessionProfilePicker  # noqa: E402
from app.traffic.domain.services.think_time_policy import ThinkTimePolicy  # noqa: E402


def build(timer: FakeTimer, spawner: InlineSpawner | None = None, load: LoadProfile | None = None, seed: int = 1):
    gateway = FakeShopGateway()
    browse = BrowseShop(gateway, timer, ThinkTimePolicy(1.0), SessionProfilePicker(DEFAULT_SESSION_PROFILES))
    spawner = spawner or InlineSpawner()
    return RunTraffic(browse, timer, Random(seed), spawner, load or LoadProfile()), spawner


def test_runs_sessions_until_the_deadline_and_waits_for_visitors() -> None:
    timer = FakeTimer()
    run, spawner = build(timer)
    report = run.execute(duration_seconds=300, sessions_per_minute=6)
    assert report.sessions == spawner.spawned > 1
    assert timer.current >= 300
    assert spawner.waited


def test_higher_rate_produces_more_sessions() -> None:
    slow = build(FakeTimer())[0].execute(600, sessions_per_minute=2)
    fast = build(FakeTimer())[0].execute(600, sessions_per_minute=20)
    assert fast.sessions > slow.sessions


def test_night_produces_fewer_sessions_than_day() -> None:
    # Jour de 20 min : 1re moitié = nuit qui monte, pic à 10 min. On compare 0-2 min (nuit) à 9-11 min (pic).
    load = LoadProfile(day_length_seconds=1200, night_factor=0.1)
    night = sum(load.factor(t) for t in range(0, 120)) / 120
    day = sum(load.factor(t) for t in range(540, 660)) / 120
    assert day > 3 * night
    quiet = build(FakeTimer(), load=load)[0].execute(120, sessions_per_minute=60)
    constant = build(FakeTimer())[0].execute(120, sessions_per_minute=60)
    assert quiet.sessions < constant.sessions


def test_same_seed_gives_same_number_of_sessions_and_requests() -> None:
    first = build(FakeTimer(), seed=7)[0].execute(300, 10)
    second = build(FakeTimer(), seed=7)[0].execute(300, 10)
    assert (first.sessions, first.requests) == (second.sessions, second.requests)


@pytest.mark.parametrize("duration, rate", [(0, 6), (-1, 6), (60, 0), (60, -2)])
def test_rejects_non_positive_parameters(duration: float, rate: float) -> None:
    with pytest.raises(ValueError):
        build(FakeTimer())[0].execute(duration, rate)
