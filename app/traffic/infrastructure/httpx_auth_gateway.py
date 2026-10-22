import httpx

from app.traffic.domain.entities.shop_response import ShopResponse
from app.traffic.domain.value_objects.account import Account
from app.traffic.infrastructure.httpx_requester import HttpxRequester

AUTH_PREFIX = "/api/auth"


class HttpxAuthGateway:
    """Adaptateur HTTP vers le service auth via la passerelle Traefik (préfixe /api/auth)."""

    def __init__(self, client: httpx.Client) -> None:
        self._requester = HttpxRequester(client, AUTH_PREFIX)

    def register(self, account: Account, correlation_id: str) -> ShopResponse:
        return self._requester.send("POST", "/register", correlation_id, json=self._credentials(account))

    def login(self, account: Account, correlation_id: str) -> ShopResponse:
        return self._requester.send("POST", "/login", correlation_id, json=self._credentials(account))

    def me(self, token: str, correlation_id: str) -> ShopResponse:
        return self._requester.send("GET", "/me", correlation_id, token=token)

    @staticmethod
    def _credentials(account: Account) -> dict[str, str]:
        return {"email": account.email, "password": account.password}
