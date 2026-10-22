import httpx

from app.traffic.domain.entities.shop_response import ShopResponse
from app.traffic.domain.enums.payment_method import PaymentMethod
from app.traffic.domain.value_objects.order_request import OrderRequest
from app.traffic.infrastructure.httpx_requester import HttpxRequester

SHOP_PREFIX = "/api/shop"
IDEMPOTENCY_HEADER = "Idempotency-Key"


class HttpxOrderGateway:
    """Adaptateur HTTP vers les commandes et le paiement du shop (le shop appelle payment en interne)."""

    def __init__(self, client: httpx.Client) -> None:
        self._requester = HttpxRequester(client, SHOP_PREFIX)

    def create_order(
        self, order: OrderRequest, idempotency_key: str, token: str | None, correlation_id: str
    ) -> ShopResponse:
        payload = {
            "email": order.email,
            "shippingAddress": {
                "fullName": order.address.full_name,
                "line1": order.address.line1,
                "postalCode": order.address.postal_code,
                "city": order.address.city,
                "country": order.address.country,
            },
            "lines": [{"productId": line.product_id, "quantity": line.quantity} for line in order.lines],
        }
        return self._requester.send(
            "POST", "/orders", correlation_id, token=token, json=payload, headers={IDEMPOTENCY_HEADER: idempotency_key}
        )

    def request_payment(self, order_id: str, token: str | None, correlation_id: str) -> ShopResponse:
        return self._requester.send("POST", f"/orders/{order_id}/pay", correlation_id, token=token)

    def confirm_payment(
        self, order_id: str, method: PaymentMethod, token: str | None, correlation_id: str
    ) -> ShopResponse:
        payload = {"payment_method": method.value}
        return self._requester.send(
            "POST", f"/orders/{order_id}/pay/confirm", correlation_id, token=token, json=payload
        )

    def lookup_order(self, order_number: str, email: str, correlation_id: str) -> ShopResponse:
        payload = {"orderNumber": order_number, "email": email}
        return self._requester.send("POST", "/orders/lookup", correlation_id, json=payload)

    def my_orders(self, token: str, correlation_id: str) -> ShopResponse:
        return self._requester.send("GET", "/me/orders", correlation_id, token=token)
