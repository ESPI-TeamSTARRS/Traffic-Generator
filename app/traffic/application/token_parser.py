from collections.abc import Mapping
from typing import Any


class TokenParser:
    """Lit le jeton d'accès d'une réponse de connexion et l'identifiant et le numéro d'une commande créée."""

    def access_token(self, body: Mapping[str, Any] | None) -> str | None:
        return self._text(body, "access_token")

    def order_id(self, body: Mapping[str, Any] | None) -> str | None:
        return self._text(body, "id")

    def order_number(self, body: Mapping[str, Any] | None) -> str | None:
        return self._text(body, "number")

    @staticmethod
    def _text(body: Mapping[str, Any] | None, key: str) -> str | None:
        value = body.get(key) if body else None
        return value if isinstance(value, str) and value else None
