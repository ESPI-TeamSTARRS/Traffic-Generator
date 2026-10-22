from random import Random
from typing import Protocol

from app.traffic.domain.value_objects.account import Account


class AccountPool(Protocol):
    """Comptes créés pendant l'exécution. Un compte n'est prêté qu'à un visiteur à la fois (pas d'échecs simultanés)."""

    def add(self, account: Account) -> None: ...

    def acquire(self, rng: Random) -> Account | None: ...

    def release(self, account: Account) -> None: ...
