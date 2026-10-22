from collections.abc import Sequence
from typing import Protocol

from app.traffic.domain.entities.shop_response import ShopResponse
from app.traffic.domain.enums.product_category import ProductCategory
from app.traffic.domain.value_objects.cart_line import CartLine


class ShopGateway(Protocol):
    """Port vers le service shop (derrière la passerelle). Chaque appel porte le correlation_id de la session."""

    def list_products(
        self, category: ProductCategory | None, page: int, page_size: int, correlation_id: str
    ) -> ShopResponse: ...

    def list_products_with_bad_query(self, correlation_id: str) -> ShopResponse:
        """Listing avec une catégorie inconnue : une erreur de saisie ou un lien périmé (le shop répond 422)."""
        ...

    def get_product(self, slug: str, correlation_id: str) -> ShopResponse: ...

    def quote_cart(self, lines: Sequence[CartLine], correlation_id: str) -> ShopResponse: ...

    def health(self, correlation_id: str) -> ShopResponse: ...
