from collections import Counter


class TrafficReport:
    """Compteurs d'une exécution : sessions de visiteurs et requêtes par code de statut."""

    def __init__(self) -> None:
        self.sessions = 0
        self.statuses: Counter[int] = Counter()

    @property
    def requests(self) -> int:
        return sum(self.statuses.values())

    def record(self, status_code: int) -> None:
        self.statuses[status_code] += 1

    def end_session(self) -> None:
        self.sessions += 1
