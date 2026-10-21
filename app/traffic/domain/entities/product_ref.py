from dataclasses import dataclass


@dataclass(frozen=True)
class ProductRef:
    """Référence minimale d'un produit lu dans le catalogue : de quoi le consulter et le mettre au panier."""

    id: str
    slug: str
