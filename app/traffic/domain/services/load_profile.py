import math
from collections.abc import Sequence

from app.traffic.domain.value_objects.burst import Burst


class LoadProfile:
    """Intensité du trafic au fil de l'exécution : jour/nuit comprimé (facultatif) et rafales légitimes.

    Le facteur jour/nuit vaut `night_factor` au début (nuit), monte jusqu'à 1 au milieu du jour (pic) et redescend ;
    sans durée de jour il vaut 1. Une rafale multiplie le facteur pendant sa durée (la plus forte l'emporte).
    """

    def __init__(
        self,
        day_length_seconds: float | None = None,
        night_factor: float = 0.15,
        bursts: Sequence[Burst] = (),
    ) -> None:
        if day_length_seconds is not None and day_length_seconds <= 0:
            raise ValueError("day_length_seconds must be positive")
        if not 0 < night_factor <= 1:
            raise ValueError("night_factor must be in ]0, 1]")
        self._day_length_seconds = day_length_seconds
        self._night_factor = night_factor
        self._bursts = tuple(bursts)

    def factor(self, elapsed_seconds: float) -> float:
        return self._daily_factor(elapsed_seconds) * self._burst_factor(elapsed_seconds)

    def _daily_factor(self, elapsed_seconds: float) -> float:
        if self._day_length_seconds is None:
            return 1.0
        phase = 0.5 - 0.5 * math.cos(2 * math.pi * elapsed_seconds / self._day_length_seconds)
        return self._night_factor + (1 - self._night_factor) * phase

    def _burst_factor(self, elapsed_seconds: float) -> float:
        return max((burst.multiplier for burst in self._bursts if burst.covers(elapsed_seconds)), default=1.0)
