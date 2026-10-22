from enum import StrEnum


class RegistrationSlip(StrEnum):
    """Erreurs de saisie courantes à l'inscription (le service répond 422, sans jamais refléter la valeur)."""

    TOO_SHORT = "weak_password"
    INVALID_EMAIL = "invalid_email"
