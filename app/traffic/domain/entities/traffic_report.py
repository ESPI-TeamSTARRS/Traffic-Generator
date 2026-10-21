from collections import Counter
from threading import Lock


class TrafficReport:
    """Compteurs d'une exécution : sessions de visiteurs et requêtes par code de statut (sûr entre threads)."""

    def __init__(self) -> None:
        self.sessions = 0
        self.statuses: Counter[int] = Counter()
        self._lock = Lock()

    @property
    def requests(self) -> int:
        return sum(self.statuses.values())

    def record(self, status_code: int) -> None:
        with self._lock:
            self.statuses[status_code] += 1

    def end_session(self) -> None:
        with self._lock:
            self.sessions += 1
