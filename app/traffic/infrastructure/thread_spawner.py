from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

MAX_PARALLEL_VISITORS = 64


class ThreadSpawner:
    """Exécute chaque session dans un thread : des visiteurs simultanés, comme sur un vrai site."""

    def __init__(self, max_workers: int = MAX_PARALLEL_VISITORS) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: list[Future[None]] = []

    def spawn(self, task: Callable[[], None]) -> None:
        self._futures.append(self._executor.submit(task))

    def wait(self) -> None:
        self._executor.shutdown(wait=True)
        for future in self._futures:
            future.result()  # relance l'erreur d'une session si elle a échoué
