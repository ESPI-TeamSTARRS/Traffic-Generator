from dataclasses import dataclass

from app.traffic.domain.value_objects.cart_line import CartLine
from app.traffic.domain.value_objects.shipping_address import ShippingAddress

MAX_LINES = 50


@dataclass(frozen=True)
class OrderRequest:
    """Commande comme l'accepte POST /orders : email, adresse et lignes (1 à 50, sans doublon, aucun prix)."""

    email: str
    address: ShippingAddress
    lines: tuple[CartLine, ...]

    def __post_init__(self) -> None:
        if not 1 <= len(self.lines) <= MAX_LINES:
            raise ValueError(f"an order needs between 1 and {MAX_LINES} lines")
        if len({line.product_id for line in self.lines}) != len(self.lines):
            raise ValueError("an order cannot contain the same product twice")
