from typing import Protocol


class Timer(Protocol):
    """Horloge et pause injectables : les tests n'attendent jamais pour de vrai."""

    def now(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...
