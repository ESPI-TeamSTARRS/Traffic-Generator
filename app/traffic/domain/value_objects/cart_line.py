from dataclasses import dataclass

MIN_QUANTITY = 1
MAX_QUANTITY = 10


@dataclass(frozen=True)
class CartLine:
    """Une ligne de panier comme l'accepte le shop : seulement un produit et une quantité (aucun prix)."""

    product_id: str
    quantity: int

    def __post_init__(self) -> None:
        if not MIN_QUANTITY <= self.quantity <= MAX_QUANTITY:
            raise ValueError(f"quantity must be between {MIN_QUANTITY} and {MAX_QUANTITY}")
