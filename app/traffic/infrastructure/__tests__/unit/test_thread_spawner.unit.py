import threading

import pytest

from app.traffic.infrastructure.thread_spawner import ThreadSpawner


def test_runs_every_task_in_parallel_threads_and_waits_for_all() -> None:
    results: list[int] = []
    threads: set[int] = set()
    barrier = threading.Barrier(3, timeout=5)  # ne passe que si 3 tâches tournent EN MÊME TEMPS

    def task(index: int) -> None:
        barrier.wait()
        threads.add(threading.get_ident())
        results.append(index)

    spawner = ThreadSpawner(max_workers=3)
    for index in range(3):
        spawner.spawn(lambda i=index: task(i))
    spawner.wait()
    assert sorted(results) == [0, 1, 2]
    assert len(threads) == 3


def test_wait_reraises_a_failed_session() -> None:
    def boom() -> None:
        raise RuntimeError("session failed")

    spawner = ThreadSpawner(max_workers=1)
    spawner.spawn(boom)
    with pytest.raises(RuntimeError, match="session failed"):
        spawner.wait()
