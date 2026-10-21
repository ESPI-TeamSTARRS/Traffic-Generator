from collections.abc import Callable
from typing import Protocol


class Spawner(Protocol):
    """Lance des sessions de visiteurs en parallèle (ou à la suite, dans les tests) et attend leur fin."""

    def spawn(self, task: Callable[[], None]) -> None: ...

    def wait(self) -> None: ...
