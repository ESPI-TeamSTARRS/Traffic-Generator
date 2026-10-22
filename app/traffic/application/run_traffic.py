from random import Random

from app.traffic.domain.entities.traffic_report import TrafficReport
from app.traffic.domain.interfaces.journey import Journey
from app.traffic.domain.interfaces.spawner import Spawner
from app.traffic.domain.interfaces.timer import Timer
from app.traffic.domain.services.load_profile import LoadProfile

SECONDS_PER_MINUTE = 60


class RunTraffic:
    """Fait arriver des visiteurs pendant une durée donnée.

    Les arrivées suivent un processus de Poisson dont le rythme (`sessions_per_minute` = rythme de pointe) varie avec
    le profil de charge (jour/nuit). Chaque visiteur est lancé en parallèle avec son propre générateur aléatoire,
    tiré du générateur principal : une même graine redonne le même trafic.
    """

    def __init__(self, journey: Journey, timer: Timer, rng: Random, spawner: Spawner, load: LoadProfile) -> None:
        self._journey = journey
        self._timer = timer
        self._rng = rng
        self._spawner = spawner
        self._load = load

    def execute(self, duration_seconds: float, sessions_per_minute: float) -> TrafficReport:
        if duration_seconds <= 0 or sessions_per_minute <= 0:
            raise ValueError("duration_seconds and sessions_per_minute must be positive")
        report = TrafficReport()
        started = self._timer.now()
        deadline = started + duration_seconds
        while self._timer.now() < deadline:
            rate = sessions_per_minute * self._load.factor(self._timer.now() - started)
            gap = self._rng.expovariate(rate / SECONDS_PER_MINUTE)
            self._timer.sleep(max(0.0, min(gap, deadline - self._timer.now())))
            if self._timer.now() >= deadline:
                break
            self._start_session(report)
        self._spawner.wait()
        return report

    def _start_session(self, report: TrafficReport) -> None:
        visitor_rng = Random(self._rng.getrandbits(64))
        self._spawner.spawn(lambda: self._journey.execute(report, visitor_rng))
