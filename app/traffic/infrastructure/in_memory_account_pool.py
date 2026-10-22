from random import Random
from threading import Lock

from app.traffic.domain.value_objects.account import Account


class InMemoryAccountPool:
    """Comptes de l'exécution en cours. Un compte prêté n'est plus proposé tant qu'il n'est pas rendu."""

    def __init__(self) -> None:
        self._available: list[Account] = []
        self._lock = Lock()

    def add(self, account: Account) -> None:
        with self._lock:
            self._available.append(account)

    def acquire(self, rng: Random) -> Account | None:
        with self._lock:
            if not self._available:
                return None
            return self._available.pop(rng.randrange(len(self._available)))

    def release(self, account: Account) -> None:
        self.add(account)
