from collections.abc import Sequence

import httpx

from app.traffic.domain.entities.shop_response import TRANSPORT_ERROR, ShopResponse
from app.traffic.domain.enums.product_category import ProductCategory
from app.traffic.domain.value_objects.cart_line import CartLine

SHOP_PREFIX = "/api/shop"
CORRELATION_HEADER = "X-Correlation-ID"


class HttpxShopGateway:
    """Adaptateur HTTP vers le shop via la passerelle Traefik (préfixe /api/shop)."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def list_products(
        self, category: ProductCategory | None, page: int, page_size: int, correlation_id: str
    ) -> ShopResponse:
        params: dict[str, str | int] = {"page": page, "page_size": page_size}
        if category is not None:
            params["category"] = category.value
        return self._send("GET", "/products", correlation_id, params=params)

    def get_product(self, slug: str, correlation_id: str) -> ShopResponse:
        return self._send("GET", f"/products/{slug}", correlation_id)

    def quote_cart(self, lines: Sequence[CartLine], correlation_id: str) -> ShopResponse:
        payload = {"lines": [{"productId": line.product_id, "quantity": line.quantity} for line in lines]}
        return self._send("POST", "/cart/quote", correlation_id, json=payload)

    def health(self, correlation_id: str) -> ShopResponse:
        return self._send("GET", "/health", correlation_id)

    def _send(self, method: str, path: str, correlation_id: str, **kwargs: object) -> ShopResponse:
        try:
            response = self._client.request(
                method, SHOP_PREFIX + path, headers={CORRELATION_HEADER: correlation_id}, **kwargs  # type: ignore[arg-type]
            )
        except httpx.HTTPError:
            return ShopResponse(status_code=TRANSPORT_ERROR)
        return ShopResponse(status_code=response.status_code, body=self._json_object(response))

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, object] | None:
        try:
            body = response.json()
        except ValueError:
            return None
        return body if isinstance(body, dict) else None
