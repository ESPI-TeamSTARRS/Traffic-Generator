from enum import StrEnum


class ProductCategory(StrEnum):
    """Catégories du catalogue shop (valeurs acceptées par GET /products?category=)."""

    TENTS = "tentes"
    SLEEPING = "couchage"
    BACKPACKS = "sacs-a-dos"
    COOKING = "cuisine"
    SAFETY = "securite"
