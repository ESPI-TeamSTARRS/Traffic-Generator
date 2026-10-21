from random import Random
from uuid import UUID

from app.traffic.application.product_parser import ProductParser
from app.traffic.domain.entities.product_ref import ProductRef
from app.traffic.domain.entities.shop_response import ShopResponse
from app.traffic.domain.entities.traffic_report import TrafficReport
from app.traffic.domain.enums.product_category import ProductCategory
from app.traffic.domain.interfaces.shop_gateway import ShopGateway
from app.traffic.domain.interfaces.timer import Timer
from app.traffic.domain.services.think_time_policy import ThinkTimePolicy
from app.traffic.domain.value_objects.cart_line import CartLine

PAGE_SIZE = 12
MAX_PRODUCTS_VIEWED = 3
MAX_CART_LINES = 3
MAX_LINE_QUANTITY = 3
QUOTE_PROBABILITY = 0.5
HEALTH_PROBABILITY = 0.1


class BrowseShop:
    """Une session de visiteur normal : parcourt le catalogue, consulte des fiches, parfois demande un devis."""

    def __init__(self, gateway: ShopGateway, timer: Timer, think_time: ThinkTimePolicy, rng: Random) -> None:
        self._gateway = gateway
        self._timer = timer
        self._think_time = think_time
        self._rng = rng
        self._parser = ProductParser()

    def execute(self, report: TrafficReport) -> None:
        correlation_id = str(UUID(int=self._rng.getrandbits(128), version=4))
        products = self._list_catalog(correlation_id, report)
        for product in self._sample(products, MAX_PRODUCTS_VIEWED):
            self._pause()
            self._record(report, self._gateway.get_product(product.slug, correlation_id))
        if products and self._rng.random() < QUOTE_PROBABILITY:
            self._pause()
            self._quote(products, correlation_id, report)
        if self._rng.random() < HEALTH_PROBABILITY:
            self._record(report, self._gateway.health(correlation_id))
        report.end_session()

    def _list_catalog(self, correlation_id: str, report: TrafficReport) -> list[ProductRef]:
        category = self._rng.choice([None, *ProductCategory])
        response = self._gateway.list_products(category, 1, PAGE_SIZE, correlation_id)
        self._record(report, response)
        return self._parser.parse(response.body) if response.is_success else []

    def _quote(self, products: list[ProductRef], correlation_id: str, report: TrafficReport) -> None:
        lines = [
            CartLine(product.id, self._rng.randint(1, MAX_LINE_QUANTITY))
            for product in self._sample(products, MAX_CART_LINES)
        ]
        self._record(report, self._gateway.quote_cart(lines, correlation_id))

    def _sample(self, products: list[ProductRef], maximum: int) -> list[ProductRef]:
        if not products:
            return []
        return self._rng.sample(products, self._rng.randint(1, min(maximum, len(products))))

    def _pause(self) -> None:
        self._timer.sleep(self._think_time.sample(self._rng))

    @staticmethod
    def _record(report: TrafficReport, response: ShopResponse) -> None:
        report.record(response.status_code)
