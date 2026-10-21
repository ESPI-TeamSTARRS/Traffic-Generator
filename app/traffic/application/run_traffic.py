from random import Random

from app.traffic.application.browse_shop import BrowseShop
from app.traffic.domain.entities.traffic_report import TrafficReport
from app.traffic.domain.interfaces.timer import Timer

SECONDS_PER_MINUTE = 60


class RunTraffic:
    """Enchaîne des sessions de visiteurs pendant une durée donnée, à un rythme nominal de sessions par minute."""

    def __init__(self, browse: BrowseShop, timer: Timer, rng: Random) -> None:
        self._browse = browse
        self._timer = timer
        self._rng = rng

    def execute(self, duration_seconds: float, sessions_per_minute: float) -> TrafficReport:
        if duration_seconds <= 0 or sessions_per_minute <= 0:
            raise ValueError("duration_seconds and sessions_per_minute must be positive")
        report = TrafficReport()
        deadline = self._timer.now() + duration_seconds
        mean_gap = SECONDS_PER_MINUTE / sessions_per_minute
        while self._timer.now() < deadline:
            started = self._timer.now()
            self._browse.execute(report)
            gap = self._rng.expovariate(1 / mean_gap)  # écart entre DÉBUTS de sessions : la durée de la session compte
            wait = min(gap - (self._timer.now() - started), deadline - self._timer.now())
            self._timer.sleep(max(0.0, wait))
        return report
