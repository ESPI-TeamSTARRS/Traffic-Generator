from random import Random

from app.traffic.domain.value_objects.shipping_address import ShippingAddress

DEFAULT_ADDRESSES = (
    ShippingAddress("Camille Martin", "12 rue des Alpes", "38000", "Grenoble", "FR"),
    ShippingAddress("Louis Dubois", "5 avenue du Mont-Blanc", "74000", "Annecy", "FR"),
    ShippingAddress("Emma Janssens", "8 rue de la Station", "1000", "Bruxelles", "BE"),
    ShippingAddress("Noah Keller", "21 Bergstrasse", "3000", "Berne", "CH"),
    ShippingAddress("Lena Schmidt", "3 Waldweg", "80331", "Munich", "DE"),
)


class AddressBook:
    """Quelques adresses de livraison fictives, tirées au hasard."""

    def __init__(self, addresses: tuple[ShippingAddress, ...] = DEFAULT_ADDRESSES) -> None:
        if not addresses:
            raise ValueError("at least one address is required")
        self._addresses = addresses

    def pick(self, rng: Random) -> ShippingAddress:
        return rng.choice(self._addresses)
