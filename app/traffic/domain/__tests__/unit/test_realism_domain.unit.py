from collections import Counter
from random import Random

import pytest

from app.traffic.domain.entities.product_ref import ProductRef
from app.traffic.domain.enums.registration_slip import RegistrationSlip
from app.traffic.domain.services.account_factory import AccountFactory
from app.traffic.domain.services.burst_planner import BurstPlanner
from app.traffic.domain.services.load_profile import LoadProfile
from app.traffic.domain.services.popularity_policy import PopularityPolicy
from app.traffic.domain.services.think_time_policy import ThinkTimePolicy
from app.traffic.domain.value_objects.account import Account
from app.traffic.domain.value_objects.burst import Burst

PRODUCTS = [ProductRef(f"p{i:02d}", f"slug-{i}") for i in range(1, 11)]


# --- Pauses longues --------------------------------------------------------------------


def test_long_pauses_stretch_the_tail_and_the_mean() -> None:
    plain, heavy = ThinkTimePolicy(2.0), ThinkTimePolicy(2.0, long_pause_probability=0.2, long_pause_mean_seconds=30)
    rng_a, rng_b = Random(1), Random(1)
    a = [plain.sample(rng_a) for _ in range(5000)]
    b = [heavy.sample(rng_b) for _ in range(5000)]
    assert sum(b) / len(b) > 2 * sum(a) / len(a)
    assert max(b) > 3 * max(a)


@pytest.mark.parametrize("kwargs", [{"long_pause_probability": 1.5}, {"long_pause_mean_seconds": 0}])
def test_think_time_rejects_invalid_long_pauses(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        ThinkTimePolicy(2.0, **kwargs)


# --- Rafales ---------------------------------------------------------------------------


def test_burst_covers_only_its_window() -> None:
    burst = Burst(start_seconds=100, duration_seconds=60, multiplier=2.5)
    assert [burst.covers(t) for t in (99, 100, 159, 160)] == [False, True, True, False]


@pytest.mark.parametrize("args", [(-1, 60, 2), (0, 0, 2), (0, 60, 1)])
def test_burst_rejects_invalid_values(args: tuple) -> None:
    with pytest.raises(ValueError):
        Burst(*args)


def test_planner_makes_about_the_requested_number_of_bursts_without_overlap() -> None:
    counts = [len(BurstPlanner(per_hour=6).plan(Random(seed), 3600 * 10)) for seed in range(20)]
    assert 40 <= sum(counts) / len(counts) <= 70  # ~6 par heure sur 10 h (marge : les rafales prennent du temps)
    bursts = BurstPlanner(per_hour=6).plan(Random(3), 3600 * 10)
    pairs = zip(bursts, bursts[1:], strict=False)
    assert all(a.start_seconds + a.duration_seconds <= b.start_seconds for a, b in pairs)
    assert all(60 <= b.duration_seconds <= 150 and 2.0 <= b.multiplier <= 3.5 for b in bursts)


def test_planner_without_bursts_and_reproducible() -> None:
    assert BurstPlanner(per_hour=0).plan(Random(1), 3600) == ()
    assert BurstPlanner(per_hour=4).plan(Random(5), 7200) == BurstPlanner(per_hour=4).plan(Random(5), 7200)


@pytest.mark.parametrize(
    "kwargs", [{"per_hour": -1}, {"per_hour": 1, "min_duration_seconds": 0}, {"per_hour": 1, "min_multiplier": 1.0}]
)
def test_planner_rejects_invalid_configuration(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        BurstPlanner(**kwargs)


def test_load_is_multiplied_during_a_burst_only() -> None:
    load = LoadProfile(bursts=[Burst(100, 60, 3.0), Burst(130, 60, 2.0)])
    assert load.factor(50) == 1.0
    assert load.factor(110) == 3.0
    assert load.factor(150) == 3.0  # deux rafales qui se chevauchent : la plus forte l'emporte
    assert load.factor(180) == 2.0
    assert load.factor(500) == 1.0


def test_burst_stacks_on_the_day_night_cycle() -> None:
    load = LoadProfile(day_length_seconds=600, night_factor=0.2, bursts=[Burst(0, 60, 2.0)])
    assert load.factor(0) == pytest.approx(0.4)  # nuit (0.2) x rafale (2)


# --- Popularité ------------------------------------------------------------------------


def test_popularity_picks_distinct_products() -> None:
    picked = PopularityPolicy().pick(PRODUCTS, 4, Random(1))
    assert len(picked) == 4 and len({p.id for p in picked}) == 4


def test_popularity_never_returns_more_than_available() -> None:
    assert len(PopularityPolicy().pick(PRODUCTS[:3], 9, Random(1))) == 3
    assert PopularityPolicy().pick([], 2, Random(1)) == []


def test_best_ranked_products_are_seen_far_more_often() -> None:
    rng, policy = Random(2), PopularityPolicy()
    seen = Counter(p.id for _ in range(3000) for p in policy.pick(PRODUCTS, 1, rng))
    assert seen["p01"] > 3 * seen["p05"] > 0 and seen["p01"] > 5 * seen["p10"]


def test_exponent_zero_is_uniform() -> None:
    rng, policy = Random(2), PopularityPolicy(exponent=0)
    seen = Counter(p.id for _ in range(5000) for p in policy.pick(PRODUCTS, 1, rng))
    assert max(seen.values()) < 1.4 * min(seen.values())


def test_popularity_rejects_a_negative_exponent() -> None:
    with pytest.raises(ValueError):
        PopularityPolicy(-1)


# --- Comptes en erreur -----------------------------------------------------------------


def test_unknown_email_is_unique_and_keeps_the_domain_and_password() -> None:
    account, rng = Account("client-abc@example.com", "Bivouac-0001-long-secret"), Random(1)
    variants = [account.with_unknown_email(rng) for _ in range(500)]
    assert len({v.email for v in variants}) == 500
    assert all(v.email.endswith("@example.com") and v.email != account.email for v in variants)
    assert all(v.password == account.password for v in variants)


def test_flawed_registrations_are_refusable() -> None:
    factory, rng = AccountFactory(), Random(1)
    short = factory.create_flawed(rng, RegistrationSlip.TOO_SHORT)
    invalid = factory.create_flawed(rng, RegistrationSlip.INVALID_EMAIL)
    assert "@" in short.email and len(short.password) < 12
    assert "@" not in invalid.email and len(invalid.password) >= 12
