from typing import Protocol

from app.traffic.domain.entities.shop_response import ShopResponse
from app.traffic.domain.value_objects.account import Account


class AuthGateway(Protocol):
    """Port vers le service auth (derrière la passerelle)."""

    def register(self, account: Account, correlation_id: str) -> ShopResponse: ...

    def login(self, account: Account, correlation_id: str) -> ShopResponse: ...

    def me(self, token: str, correlation_id: str) -> ShopResponse: ...
