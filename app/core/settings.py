import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class Settings:
    """Configuration par variables d'environnement TG_* (aucun secret : la cible est la passerelle publique)."""

    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            base_url=os.environ.get("TG_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            timeout_seconds=float(os.environ.get("TG_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)),
        )
