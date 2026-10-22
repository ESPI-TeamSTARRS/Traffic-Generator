from random import Random
from typing import Protocol

from app.traffic.domain.entities.traffic_report import TrafficReport


class Journey(Protocol):
    """Un parcours de visiteur, du début à la fin (invité, nouveau client, client connu...)."""

    def execute(self, report: TrafficReport, rng: Random) -> None: ...
