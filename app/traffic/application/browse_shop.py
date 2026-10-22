from random import Random

from app.traffic.application.product_parser import ProductParser
from app.traffic.domain.entities.product_ref import ProductRef
from app.traffic.domain.entities.shop_response import ShopResponse
from app.traffic.domain.entities.traffic_report import TrafficReport
from app.traffic.domain.enums.product_category import ProductCategory
from app.traffic.domain.interfaces.shop_gateway import ShopGateway
from app.traffic.domain.interfaces.timer import Timer
from app.traffic.domain.services.correlation_id_factory import CorrelationIdFactory
from app.traffic.domain.services.popularity_policy import PopularityPolicy
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
UNKNOWN_PRODUCT_ID = "produit-fantome"  # identifiant absent du catalogue : devis refusé (product_not_found)


class BrowseShop:
    """Une session de visiteur : le profil tiré décide du nombre de listings, de fiches vues et du devis.

    Avec `refusal_probability`, la session contient parfois une consultation d'un produit inexistant : un refus
    normal (lien périmé, faute de frappe) que le détecteur doit apprendre à tolérer. Avec `slip_probability`, le
    visiteur fait aussi parfois une erreur de saisie : listing avec une catégorie inconnue ou devis invalide (un
    produit en double ou inconnu), tous deux refusés en 422 par le shop.
    `popularity` fait que les produits ne sont pas vus à égalité (quelques-uns concentrent les visites).
    """

    def __init__(
        self,
        gateway: ShopGateway,
        timer: Timer,
        think_time: ThinkTimePolicy,
        picker: SessionProfilePicker,
        refusal_probability: float = 0.0,
        popularity: PopularityPolicy | None = None,
        slip_probability: float = 0.0,
    ) -> None:
        for name, value in (("refusal_probability", refusal_probability), ("slip_probability", slip_probability)):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        self._gateway = gateway
        self._timer = timer
        self._think_time = think_time
        self._picker = picker
        self._refusal_probability = refusal_probability
        self._popularity = popularity
        self._slip_probability = slip_probability
        self._parser = ProductParser()
        self._ids = CorrelationIdFactory()

    def execute(self, report: TrafficReport, rng: Random) -> None:
        """Session d'un visiteur invité : navigation, puis parfois un refus normal et un contrôle de santé."""
        correlation_id = self._ids.create(rng)
        self.browse(report, rng, correlation_id)
        if rng.random() < self._refusal_probability:
            self._pause(rng)
            self._record(report, self._gateway.get_product(UNKNOWN_SLUG, correlation_id))
        if rng.random() < HEALTH_PROBABILITY:
            self._record(report, self._gateway.health(correlation_id))
        report.end_session()

    def browse(self, report: TrafficReport, rng: Random, correlation_id: str) -> list[ProductRef]:
        """Navigation d'un profil tiré : listings, fiches, devis éventuel. Renvoie les produits vus (pour commander)."""
        profile = self._picker.pick(rng)
        products = self._browse_catalog(profile, correlation_id, report, rng)
        self._view_products(profile, products, correlation_id, report, rng)
        if products and rng.random() < profile.quote_probability:
            self._pause(rng)
            self._record(report, self._gateway.quote_cart(self._cart(products, rng), correlation_id))
        if rng.random() < self._slip_probability:
            self._pause(rng)
            self._slip(products, correlation_id, report, rng)
        return products

    def _slip(self, products: list[ProductRef], correlation_id: str, report: TrafficReport, rng: Random) -> None:
        """Une erreur de saisie : listing avec une catégorie inconnue, ou devis invalide si des produits ont été vus."""
        if not products or rng.random() < 0.5:
            self._record(report, self._gateway.list_products_with_bad_query(correlation_id))
            return
        duplicate = [CartLine(products[0].id, 1)] * 2
        unknown = [CartLine(UNKNOWN_PRODUCT_ID, 1)]
        self._record(report, self._gateway.quote_cart(rng.choice([duplicate, unknown]), correlation_id))

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
        for product in self._choose(products, count, rng):
            self._pause(rng)
            self._record(report, self._gateway.get_product(product.slug, correlation_id))

    def _cart(self, products: list[ProductRef], rng: Random) -> list[CartLine]:
        chosen = self._choose(products, rng.randint(1, min(MAX_CART_LINES, len(products))), rng)
        return [CartLine(product.id, rng.randint(1, MAX_LINE_QUANTITY)) for product in chosen]

    def _choose(self, products: list[ProductRef], count: int, rng: Random) -> list[ProductRef]:
        if self._popularity is not None:
            return self._popularity.pick(products, count, rng)
        return rng.sample(products, count)

    def _pause(self, rng: Random) -> None:
        self._timer.sleep(self._think_time.sample(rng))

    @staticmethod
    def _record(report: TrafficReport, response: ShopResponse) -> None:
        report.record(response.status_code)
