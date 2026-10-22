from random import Random


class ThinkTimePolicy:
    """Temps de réflexion d'un visiteur entre deux actions : loi exponentielle, donc irrégulier comme un humain.

    Avec `long_pause_probability`, certaines pauses sont beaucoup plus longues (lecture, café, onglet oublié) :
    la durée des sessions a alors une longue traîne, comme sur un vrai site.
    """

    def __init__(
        self, mean_seconds: float, long_pause_probability: float = 0.0, long_pause_mean_seconds: float = 20.0
    ) -> None:
        if mean_seconds <= 0 or long_pause_mean_seconds <= 0:
            raise ValueError("mean durations must be positive")
        if not 0 <= long_pause_probability <= 1:
            raise ValueError("long_pause_probability must be between 0 and 1")
        self._mean_seconds = mean_seconds
        self._long_pause_probability = long_pause_probability
        self._long_pause_mean_seconds = long_pause_mean_seconds

    def sample(self, rng: Random) -> float:
        mean = self._long_pause_mean_seconds if rng.random() < self._long_pause_probability else self._mean_seconds
        return rng.expovariate(1 / mean)
