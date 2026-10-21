from random import Random
from uuid import UUID

from app.traffic.application.product_parser import ProductParser
from app.traffic.domain.entities.product_ref import ProductRef
from app.traffic.domain.entities.shop_response import ShopResponse
from app.traffic.domain.entities.traffic_report import TrafficReport
from app.traffic.domain.enums.product_category import ProductCategory
from app.traffic.domain.interfaces.shop_gateway import ShopGateway
from app.traffic.domain.interfaces.timer import Timer
from app.traffic.domain.services.session_profile_picker import SessionProfilePicker
from app.traffic.domain.services.think_time_policy import ThinkTimePolicy
from app.traffic.domain.value_objects.cart_line import CartLine
from app.traffic.domain.value_objects.session_profile import SessionProfile

PAGE_SIZE = 12
MAX_CART_LINES = 3
MAX_LINE_QUANTITY = 3
HEALTH_PROBABILITY = 0.1
# Slug absent du catalogue : le shop répond 404 et journalise un refus (catalog.product_not_found).
UNKNOWN_SLUG = "article-introuvable"


class BrowseShop:
    """Une session de visiteur : le profil tiré décide du nombre de listings, de fiches vues et du devis.

    Avec `refusal_probability`, la session contient parfois une consultation d'un produit inexistant : un refus
    normal (lien périmé, faute de frappe) que le détecteur doit apprendre à tolérer.
    """

    def __init__(
        self,
        gateway: ShopGateway,
        timer: Timer,
        think_time: ThinkTimePolicy,
        picker: SessionProfilePicker,
        refusal_probability: float = 0.0,
    ) -> None:
        if not 0 <= refusal_probability <= 1:
            raise ValueError("refusal_probability must be between 0 and 1")
        self._gateway = gateway
        self._timer = timer
        self._think_time = think_time
        self._picker = picker
        self._refusal_probability = refusal_probability
        self._parser = ProductParser()

    def execute(self, report: TrafficReport, rng: Random) -> None:
        profile = self._picker.pick(rng)
        correlation_id = str(UUID(int=rng.getrandbits(128), version=4))
        products = self._browse_catalog(profile, correlation_id, report, rng)
        self._view_products(profile, products, correlation_id, report, rng)
        if products and rng.random() < profile.quote_probability:
            self._pause(rng)
            self._record(report, self._gateway.quote_cart(self._cart(products, rng), correlation_id))
        if rng.random() < self._refusal_probability:
            self._pause(rng)
            self._record(report, self._gateway.get_product(UNKNOWN_SLUG, correlation_id))
        if rng.random() < HEALTH_PROBABILITY:
            self._record(report, self._gateway.health(correlation_id))
        report.end_session()

    def _browse_catalog(
        self, profile: SessionProfile, correlation_id: str, report: TrafficReport, rng: Random
    ) -> list[ProductRef]:
        products: dict[str, ProductRef] = {}
        for listing in range(profile.listings):
            if listing:
                self._pause(rng)
            category = rng.choice([None, *ProductCategory])
            response = self._gateway.list_products(category, 1, PAGE_SIZE, correlation_id)
            self._record(report, response)
            if response.is_success:
                products.update({ref.id: ref for ref in self._parser.parse(response.body)})
        return list(products.values())

    def _view_products(
        self,
        profile: SessionProfile,
        products: list[ProductRef],
        correlation_id: str,
        report: TrafficReport,
        rng: Random,
    ) -> None:
        count = min(rng.randint(profile.min_views, profile.max_views), len(products))
        for product in rng.sample(products, count):
            self._pause(rng)
            self._record(report, self._gateway.get_product(product.slug, correlation_id))

    @staticmethod
    def _cart(products: list[ProductRef], rng: Random) -> list[CartLine]:
        chosen = rng.sample(products, rng.randint(1, min(MAX_CART_LINES, len(products))))
        return [CartLine(product.id, rng.randint(1, MAX_LINE_QUANTITY)) for product in chosen]

    def _pause(self, rng: Random) -> None:
        self._timer.sleep(self._think_time.sample(rng))

    @staticmethod
    def _record(report: TrafficReport, response: ShopResponse) -> None:
        report.record(response.status_code)
