from threading import Lock

from app.traffic.domain.interfaces.timer import Timer

SECONDS_PER_MINUTE = 60


class TokenBucket:
    """Limiteur de débit côté client : reste sous les limites de la passerelle (par IP) au lieu de les dépasser.

    Le seau se remplit à `per_minute` jetons par minute jusqu'à `burst`. `try_acquire` refuse (sans attendre) quand il
    n'y a pas assez de jetons : le visiteur renonce alors à l'action plutôt que de provoquer un 429.
    """

    def __init__(self, timer: Timer, per_minute: float, burst: int) -> None:
        if per_minute <= 0 or burst < 1:
            raise ValueError("per_minute must be positive and burst at least 1")
        self._timer = timer
        self._per_second = per_minute / SECONDS_PER_MINUTE
        self._burst = burst
        self._tokens = float(burst)
        self._last = timer.now()
        self._lock = Lock()

    def try_acquire(self, cost: int = 1) -> bool:
        if not 1 <= cost <= self._burst:
            raise ValueError("cost must be between 1 and burst")
        with self._lock:
            now = self._timer.now()
            self._tokens = min(self._burst, self._tokens + (now - self._last) * self._per_second)
            self._last = now
            if self._tokens < cost:
                return False
            self._tokens -= cost
            return True
