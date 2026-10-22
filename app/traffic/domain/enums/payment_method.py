from enum import StrEnum


class PaymentMethod(StrEnum):
    """Méthodes de test acceptées par POST /orders/{id}/pay/confirm (aucune donnée bancaire)."""

    SUCCESS = "pm_test_success"
    DECLINED = "pm_test_declined"
