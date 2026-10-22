from collections.abc import Sequence
from random import Random

from app.traffic.domain.entities.traffic_report import TrafficReport
from app.traffic.domain.interfaces.journey import Journey


class JourneyMix:
    """Tire le parcours de chaque visiteur selon des poids (invité, nouveau client, client connu...)."""

    def __init__(self, journeys: Sequence[tuple[float, Journey]]) -> None:
        if not journeys or any(weight <= 0 for weight, _ in journeys):
            raise ValueError("journeys need at least one entry, each with a positive weight")
        self._weights = [weight for weight, _ in journeys]
        self._journeys = [journey for _, journey in journeys]

    def execute(self, report: TrafficReport, rng: Random) -> None:
        rng.choices(self._journeys, weights=self._weights)[0].execute(report, rng)
