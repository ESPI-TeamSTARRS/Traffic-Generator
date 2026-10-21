from collections.abc import Sequence

from app.traffic.domain.entities.shop_response import ShopResponse
from app.traffic.domain.enums.product_category import ProductCategory
from app.traffic.domain.value_objects.cart_line import CartLine

CATALOG_BODY = {
    "items": [
        {"id": "p1", "slug": "tente-a"},
        {"id": "p2", "slug": "sac-b"},
        {"id": "p3", "slug": "duvet-c"},
    ]
}


class FakeShopGateway:
    """Enregistre les appels (nom, argument) et renvoie des réponses programmables."""

    def __init__(self, catalog: ShopResponse | None = None, default_status: int = 200) -> None:
        self.calls: list[tuple[str, object]] = []
        self.correlation_ids: list[str] = []
        self._catalog = catalog or ShopResponse(200, CATALOG_BODY)
        self._default_status = default_status

    def list_products(
        self, category: ProductCategory | None, page: int, page_size: int, correlation_id: str
    ) -> ShopResponse:
        self._note("list_products", (category, page, page_size), correlation_id)
        return self._catalog

    def get_product(self, slug: str, correlation_id: str) -> ShopResponse:
        self._note("get_product", slug, correlation_id)
        return ShopResponse(self._default_status)

    def quote_cart(self, lines: Sequence[CartLine], correlation_id: str) -> ShopResponse:
        self._note("quote_cart", tuple(lines), correlation_id)
        return ShopResponse(self._default_status)

    def health(self, correlation_id: str) -> ShopResponse:
        self._note("health", None, correlation_id)
        return ShopResponse(self._default_status)

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]

    def _note(self, name: str, argument: object, correlation_id: str) -> None:
        self.calls.append((name, argument))
        self.correlation_ids.append(correlation_id)


class FakeTimer:
    """Temps simulé : sleep avance l'horloge sans attendre."""

    def __init__(self) -> None:
        self.current = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += seconds
