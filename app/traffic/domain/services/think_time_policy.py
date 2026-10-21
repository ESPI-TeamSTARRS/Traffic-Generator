from random import Random


class ThinkTimePolicy:
    """Temps de réflexion d'un visiteur entre deux actions : loi exponentielle, donc irrégulier comme un humain."""

    def __init__(self, mean_seconds: float) -> None:
        if mean_seconds <= 0:
            raise ValueError("mean_seconds must be positive")
        self._mean_seconds = mean_seconds

    def sample(self, rng: Random) -> float:
        return rng.expovariate(1 / self._mean_seconds)
