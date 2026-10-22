from collections.abc import Sequence

import httpx

from app.traffic.domain.entities.shop_response import ShopResponse
from app.traffic.domain.enums.product_category import ProductCategory
from app.traffic.domain.value_objects.cart_line import CartLine
from app.traffic.infrastructure.httpx_requester import HttpxRequester

SHOP_PREFIX = "/api/shop"


class HttpxShopGateway:
    """Adaptateur HTTP vers le catalogue et les devis du shop via la passerelle Traefik (préfixe /api/shop)."""

    def __init__(self, client: httpx.Client) -> None:
        self._requester = HttpxRequester(client, SHOP_PREFIX)

    def list_products(
        self, category: ProductCategory | None, page: int, page_size: int, correlation_id: str
    ) -> ShopResponse:
        params: dict[str, str | int] = {"page": page, "page_size": page_size}
        if category is not None:
            params["category"] = category.value
        return self._requester.send("GET", "/products", correlation_id, params=params)

    def list_products_with_bad_query(self, correlation_id: str) -> ShopResponse:
        return self._requester.send("GET", "/products", correlation_id, params={"category": "categorie-inconnue"})

    def get_product(self, slug: str, correlation_id: str) -> ShopResponse:
        return self._requester.send("GET", f"/products/{slug}", correlation_id)

    def quote_cart(self, lines: Sequence[CartLine], correlation_id: str) -> ShopResponse:
        payload = {"lines": [{"productId": line.product_id, "quantity": line.quantity} for line in lines]}
        return self._requester.send("POST", "/cart/quote", correlation_id, json=payload)

    def health(self, correlation_id: str) -> ShopResponse:
        return self._requester.send("GET", "/health", correlation_id)
