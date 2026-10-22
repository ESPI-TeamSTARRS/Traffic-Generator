from dataclasses import dataclass


@dataclass(frozen=True)
class ShippingAddress:
    """Adresse de livraison fictive, dans les pays acceptés par le shop (FR, BE, CH, LU, DE, ES, IT)."""

    full_name: str
    line1: str
    postal_code: str
    city: str
    country: str
