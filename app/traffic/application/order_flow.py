from random import Random

from app.traffic.application.token_parser import TokenParser
from app.traffic.domain.entities.product_ref import ProductRef
from app.traffic.domain.entities.traffic_report import TrafficReport
from app.traffic.domain.enums.payment_method import PaymentMethod
from app.traffic.domain.interfaces.order_gateway import OrderGateway
from app.traffic.domain.interfaces.timer import Timer
from app.traffic.domain.services.address_book import AddressBook
from app.traffic.domain.services.popularity_policy import PopularityPolicy
from app.traffic.domain.services.think_time_policy import ThinkTimePolicy
from app.traffic.domain.services.token_bucket import TokenBucket
from app.traffic.domain.value_objects.cart_line import CartLine
from app.traffic.domain.value_objects.order_request import OrderRequest

FIRST_ATTEMPT_COST = 3  # créer la commande, demander le paiement, le confirmer : 3 requêtes sous /api/shop/orders
RETRY_COST = 2  # nouvelle demande de paiement et nouvelle confirmation
EXTRA_COST = 1  # rejeu, double confirmation ou suivi : une requête de plus sous /api/shop/orders
MAX_CART_LINES = 2
RETRY_AFTER_DECLINE_PROBABILITY = 0.5
LOOKUP_PROBABILITY = 0.15
WRONG_EMAIL_LOOKUP_PROBABILITY = 0.3


class OrderFlow:
    """Commande puis paiement (par le shop, qui appelle payment). Reste sous la limite de débit de la passerelle.

    La passerelle limite tout `/api/shop/orders*` (création, paiement, suivi) à 10 requêtes par minute et par IP :
    chaque action consomme des jetons du limiteur et le visiteur y renonce s'il n'y en a plus.

    Comme dans la vraie vie, tout n'aboutit pas : une part des commandes n'est jamais payée (`abandon_probability`,
    elles expirent) et une part des paiements est refusée (méthode de test `pm_test_declined`).
    Avec `slip_probability`, le visiteur fait aussi des gestes maladroits : double clic sur « commander » (même clé
    d'idempotence, le shop renvoie la même commande), double confirmation du paiement (409) et suivi de commande avec
    une adresse erronée (404).
    """

    def __init__(
        self,
        orders: OrderGateway,
        timer: Timer,
        think_time: ThinkTimePolicy,
        addresses: AddressBook,
        limiter: TokenBucket,
        order_probability: float,
        decline_probability: float,
        abandon_probability: float = 0.0,
        slip_probability: float = 0.0,
        popularity: PopularityPolicy | None = None,
    ) -> None:
        for name, value in (
            ("order_probability", order_probability),
            ("decline_probability", decline_probability),
            ("abandon_probability", abandon_probability),
            ("slip_probability", slip_probability),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        self._orders = orders
        self._timer = timer
        self._think_time = think_time
        self._addresses = addresses
        self._limiter = limiter
        self._order_probability = order_probability
        self._decline_probability = decline_probability
        self._abandon_probability = abandon_probability
        self._slip_probability = slip_probability
        self._popularity = popularity
        self._parser = TokenParser()

    def place(
        self,
        products: list[ProductRef],
        email: str,
        token: str | None,
        correlation_id: str,
        report: TrafficReport,
        rng: Random,
    ) -> None:
        if not products or rng.random() >= self._order_probability or not self._limiter.try_acquire(FIRST_ATTEMPT_COST):
            return
        self._pause(rng)
        order = OrderRequest(email, self._addresses.pick(rng), self._lines(products, rng))
        key = f"tg-{rng.getrandbits(96):024x}"
        response = self._orders.create_order(order, key, token, correlation_id)
        report.record(response.status_code)
        order_id = self._parser.order_id(response.body)
        if not (response.is_success and order_id):
            return
        self._double_click(order, key, token, correlation_id, report, rng)
        self._track(self._parser.order_number(response.body), email, correlation_id, report, rng)
        if rng.random() < self._abandon_probability:
            return  # commande jamais payée : le shop la fera expirer et rendra le stock
        self._pay(order_id, token, correlation_id, report, rng)

    def _pay(self, order_id: str, token: str | None, correlation_id: str, report: TrafficReport, rng: Random) -> None:
        declined = rng.random() < self._decline_probability
        method = PaymentMethod.DECLINED if declined else PaymentMethod.SUCCESS
        if not self._attempt(order_id, method, token, correlation_id, report, rng):
            return
        if not declined:
            self._double_confirm(order_id, token, correlation_id, report, rng)
        elif rng.random() < RETRY_AFTER_DECLINE_PROBABILITY and self._limiter.try_acquire(RETRY_COST):
            self._attempt(order_id, PaymentMethod.SUCCESS, token, correlation_id, report, rng, abandonable=False)

    def _attempt(
        self,
        order_id: str,
        method: PaymentMethod,
        token: str | None,
        correlation_id: str,
        report: TrafficReport,
        rng: Random,
        abandonable: bool = True,
    ) -> bool:
        """Demande puis confirme un paiement. Renvoie True si les deux appels ont abouti (2xx)."""
        self._pause(rng)
        requested = self._orders.request_payment(order_id, token, correlation_id)
        report.record(requested.status_code)
        if not requested.is_success:
            return False
        if abandonable and rng.random() < self._abandon_probability / 2:
            return False  # il quitte la page de paiement sans confirmer
        self._pause(rng)
        confirmed = self._orders.confirm_payment(order_id, method, token, correlation_id)
        report.record(confirmed.status_code)
        return confirmed.is_success

    def _double_click(
        self, order: OrderRequest, key: str, token: str | None, correlation_id: str, report: TrafficReport, rng: Random
    ) -> None:
        """Deuxième clic sur « commander » : même clé, le shop renvoie la même commande (200), sans doublon."""
        if rng.random() < self._slip_probability and self._limiter.try_acquire(EXTRA_COST):
            report.record(self._orders.create_order(order, key, token, correlation_id).status_code)

    def _double_confirm(
        self, order_id: str, token: str | None, correlation_id: str, report: TrafficReport, rng: Random
    ) -> None:
        """Confirme une seconde fois une commande déjà payée : le shop répond 409."""
        if rng.random() < self._slip_probability and self._limiter.try_acquire(EXTRA_COST):
            response = self._orders.confirm_payment(order_id, PaymentMethod.SUCCESS, token, correlation_id)
            report.record(response.status_code)

    def _track(self, number: str | None, email: str, correlation_id: str, report: TrafficReport, rng: Random) -> None:
        """Suivi par numéro et email ; parfois une adresse erronée (404, identique à un numéro inconnu)."""
        if not number or rng.random() >= LOOKUP_PROBABILITY or not self._limiter.try_acquire(EXTRA_COST):
            return
        wrong = self._slip_probability > 0 and rng.random() < WRONG_EMAIL_LOOKUP_PROBABILITY
        report.record(
            self._orders.lookup_order(number, email.replace("@", "-x@") if wrong else email, correlation_id).status_code
        )

    def _lines(self, products: list[ProductRef], rng: Random) -> tuple[CartLine, ...]:
        count = rng.randint(1, min(MAX_CART_LINES, len(products)))
        chosen = self._popularity.pick(products, count, rng) if self._popularity else rng.sample(products, count)
        return tuple(CartLine(product.id, 1) for product in chosen)  # quantité 1 : le stock du catalogue est limité

    def _pause(self, rng: Random) -> None:
        self._timer.sleep(self._think_time.sample(rng))
