from http.cookiejar import DefaultCookiePolicy

import httpx

from app.traffic.domain.entities.shop_response import TRANSPORT_ERROR, ShopResponse

CORRELATION_HEADER = "X-Correlation-ID"


def build_client(base_url: str, timeout_seconds: float) -> httpx.Client:
    """Client HTTP sans mémoire de cookies : les visiteurs sont simultanés, ils ne doivent pas partager de session."""
    client = httpx.Client(base_url=base_url, timeout=timeout_seconds)
    client.cookies.jar.set_policy(DefaultCookiePolicy(allowed_domains=[]))  # liste vide : aucun cookie accepté
    return client


class HttpxRequester:
    """Envoie une requête sous un préfixe de passerelle et renvoie un ShopResponse (statut 0 si le réseau échoue)."""

    def __init__(self, client: httpx.Client, prefix: str) -> None:
        self._client = client
        self._prefix = prefix

    def send(
        self, method: str, path: str, correlation_id: str, token: str | None = None, **kwargs: object
    ) -> ShopResponse:
        headers = {CORRELATION_HEADER: correlation_id, **kwargs.pop("headers", {})}  # type: ignore[call-overload]
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = self._client.request(method, self._prefix + path, headers=headers, **kwargs)  # type: ignore[arg-type]
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
