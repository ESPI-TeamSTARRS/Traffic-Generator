from random import Random

from app.traffic.application.browse_shop import BrowseShop
from app.traffic.application.order_flow import OrderFlow
from app.traffic.domain.entities.traffic_report import TrafficReport
from app.traffic.domain.interfaces.auth_gateway import AuthGateway
from app.traffic.domain.interfaces.order_gateway import OrderGateway

MY_ORDERS_PROBABILITY = 0.5


class CustomerSession:
    """Ce que fait un client connecté : consulte son profil, parcourt le catalogue, commande, relit ses commandes."""

    def __init__(
        self, auth: AuthGateway, orders: OrderGateway, browse: BrowseShop, order_flow: OrderFlow
    ) -> None:
        self._auth = auth
        self._orders = orders
        self._browse = browse
        self._order_flow = order_flow

    def run(self, email: str, token: str, correlation_id: str, report: TrafficReport, rng: Random) -> None:
        report.record(self._auth.me(token, correlation_id).status_code)
        products = self._browse.browse(report, rng, correlation_id)
        self._order_flow.place(products, email, token, correlation_id, report, rng)
        if rng.random() < MY_ORDERS_PROBABILITY:
            report.record(self._orders.my_orders(token, correlation_id).status_code)
