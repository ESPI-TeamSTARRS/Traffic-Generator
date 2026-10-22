from typing import Protocol

from app.traffic.domain.entities.shop_response import ShopResponse
from app.traffic.domain.enums.payment_method import PaymentMethod
from app.traffic.domain.value_objects.order_request import OrderRequest


class OrderGateway(Protocol):
    """Port vers les commandes et le paiement du shop. Le jeton est facultatif (commande invité)."""

    def create_order(
        self, order: OrderRequest, idempotency_key: str, token: str | None, correlation_id: str
    ) -> ShopResponse: ...

    def request_payment(self, order_id: str, token: str | None, correlation_id: str) -> ShopResponse: ...

    def confirm_payment(
        self, order_id: str, method: PaymentMethod, token: str | None, correlation_id: str
    ) -> ShopResponse: ...

    def lookup_order(self, order_number: str, email: str, correlation_id: str) -> ShopResponse:
        """Suivi d'une commande par son numéro et son email (parcours invité)."""
        ...

    def my_orders(self, token: str, correlation_id: str) -> ShopResponse: ...
