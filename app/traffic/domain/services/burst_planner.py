from random import Random

from app.traffic.domain.value_objects.burst import Burst

SECONDS_PER_HOUR = 3600


class BurstPlanner:
    """Tire à l'avance les rafales d'une exécution : en moyenne `per_hour` par heure, jamais deux qui se chevauchent."""

    def __init__(
        self,
        per_hour: float,
        min_duration_seconds: float = 60.0,
        max_duration_seconds: float = 150.0,
        min_multiplier: float = 2.0,
        max_multiplier: float = 3.5,
    ) -> None:
        if per_hour < 0:
            raise ValueError("per_hour must not be negative")
        if not 0 < min_duration_seconds <= max_duration_seconds or not 1 < min_multiplier <= max_multiplier:
            raise ValueError("invalid duration or multiplier range")
        self._per_hour = per_hour
        self._durations = (min_duration_seconds, max_duration_seconds)
        self._multipliers = (min_multiplier, max_multiplier)

    def plan(self, rng: Random, horizon_seconds: float) -> tuple[Burst, ...]:
        if self._per_hour == 0:
            return ()
        mean_gap = SECONDS_PER_HOUR / self._per_hour
        bursts: list[Burst] = []
        cursor = rng.expovariate(1 / mean_gap)
        while cursor < horizon_seconds:
            duration = rng.uniform(*self._durations)
            bursts.append(Burst(cursor, duration, rng.uniform(*self._multipliers)))
            cursor += duration + rng.expovariate(1 / mean_gap)
        return tuple(bursts)
