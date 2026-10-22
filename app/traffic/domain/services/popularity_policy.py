from random import Random

from app.traffic.domain.entities.product_ref import ProductRef


class PopularityPolicy:
    """Tous les produits ne se valent pas : quelques-uns attirent l'essentiel des visites (loi de Zipf).

    Le rang d'un produit est fixe (ordre de son identifiant) : le même produit est populaire dans toutes les sessions.
    """

    def __init__(self, exponent: float = 1.0) -> None:
        if exponent < 0:
            raise ValueError("exponent must not be negative")
        self._exponent = exponent

    def pick(self, products: list[ProductRef], count: int, rng: Random) -> list[ProductRef]:
        """Tire `count` produits distincts, les mieux classés étant les plus probables."""
        remaining = sorted(products, key=lambda product: product.id)
        chosen: list[ProductRef] = []
        for _ in range(min(count, len(remaining))):
            weights = [1 / (rank + 1) ** self._exponent for rank in range(len(remaining))]
            chosen.append(remaining.pop(rng.choices(range(len(remaining)), weights=weights)[0]))
        return chosen
