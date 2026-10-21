import math


class LoadProfile:
    """Intensité du trafic selon l'heure simulée : un « jour » comprimé en quelques minutes.

    Le facteur vaut `night_factor` au début (nuit), monte jusqu'à 1 au milieu du jour (pic) et redescend.
    Sans durée de jour, le trafic est constant (facteur 1).
    """

    def __init__(self, day_length_seconds: float | None = None, night_factor: float = 0.15) -> None:
        if day_length_seconds is not None and day_length_seconds <= 0:
            raise ValueError("day_length_seconds must be positive")
        if not 0 < night_factor <= 1:
            raise ValueError("night_factor must be in ]0, 1]")
        self._day_length_seconds = day_length_seconds
        self._night_factor = night_factor

    def factor(self, elapsed_seconds: float) -> float:
        if self._day_length_seconds is None:
            return 1.0
        phase = 0.5 - 0.5 * math.cos(2 * math.pi * elapsed_seconds / self._day_length_seconds)
        return self._night_factor + (1 - self._night_factor) * phase
