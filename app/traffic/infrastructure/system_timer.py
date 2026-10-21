import time


class SystemTimer:
    """Horloge réelle : temps monotone et pause bloquante."""

    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
