from dataclasses import dataclass


@dataclass(frozen=True)
class Burst:
    """Rafale de visiteurs légitime (mailing, promotion, article repris) : le trafic est multiplié un court moment."""

    start_seconds: float
    duration_seconds: float
    multiplier: float

    def __post_init__(self) -> None:
        if self.start_seconds < 0 or self.duration_seconds <= 0 or self.multiplier <= 1:
            raise ValueError("a burst needs start >= 0, duration > 0 and multiplier > 1")

    def covers(self, elapsed_seconds: float) -> bool:
        return self.start_seconds <= elapsed_seconds < self.start_seconds + self.duration_seconds
