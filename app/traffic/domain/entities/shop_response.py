from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

TRANSPORT_ERROR = 0


@dataclass(frozen=True)
class ShopResponse:
    """Réponse du shop vue par le générateur. Le statut 0 signale une erreur réseau (pas de réponse)."""

    status_code: int
    body: Mapping[str, Any] | None = None

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300
