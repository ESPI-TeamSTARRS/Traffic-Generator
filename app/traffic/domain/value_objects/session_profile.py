from dataclasses import dataclass


@dataclass(frozen=True)
class SessionProfile:
    """Type de visiteur : combien de listings, de fiches consultées, et s'il demande un devis."""

    name: str
    weight: float
    listings: int
    min_views: int
    max_views: int
    quote_probability: float

    def __post_init__(self) -> None:
        if self.weight <= 0 or self.listings < 1:
            raise ValueError("weight must be positive and listings at least 1")
        if not 0 <= self.min_views <= self.max_views:
            raise ValueError("views must satisfy 0 <= min_views <= max_views")
        if not 0 <= self.quote_probability <= 1:
            raise ValueError("quote_probability must be between 0 and 1")
