from random import Random

from app.traffic.domain.entities.shop_response import ShopResponse
from app.traffic.domain.enums.payment_method import PaymentMethod
from app.traffic.domain.value_objects.account import Account
from app.traffic.domain.value_objects.order_request import OrderRequest


class FakeAuthGateway:
    """Enregistre les appels ; inscription 202, connexion 200 avec jeton si le mot de passe est celui du compte."""

    def __init__(self, register_status: int = 202) -> None:
        self.calls: list[tuple[str, str]] = []   # (action, email ou jeton)
        self.passwords: dict[str, str] = {}
        self.failed_logins = 0
        self._register_status = register_status

    def register(self, account: Account, correlation_id: str) -> ShopResponse:
        self.calls.append(("register", account.email))
        if "@" not in account.email or len(account.password) < 12:
            return ShopResponse(422)        # adresse invalide ou mot de passe trop court
        if self._register_status == 202:
            self.passwords.setdefault(account.email, account.password)
        return ShopResponse(self._register_status)

    def login(self, account: Account, correlation_id: str) -> ShopResponse:
        self.calls.append(("login", account.email))
        if self.passwords.get(account.email) == account.password:
            return ShopResponse(200, {"access_token": f"jeton-{account.email}"})
        self.failed_logins += 1
        return ShopResponse(401, {"detail": "Identifiants invalides."})

    def me(self, token: str, correlation_id: str) -> ShopResponse:
        self.calls.append(("me", token))
        return ShopResponse(200, {"email": token.removeprefix("jeton-")})

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]


class FakeOrderGateway:
    """Enregistre les commandes et paiements ; les statuts de réponse sont programmables."""

    def __init__(self, create_status: int = 201, pay_status: int = 201, confirm_status: int = 200) -> None:
        self.calls: list[tuple[str, object]] = []
        self.orders: list[OrderRequest] = []
        self.keys: list[str] = []
        self.tokens: list[str | None] = []
        self.methods: list[PaymentMethod] = []
        self._statuses = (create_status, pay_status, confirm_status)

    def create_order(self, order, idempotency_key, token, correlation_id):
        self.calls.append(("create_order", order.email))
        self.orders.append(order)
        self.keys.append(idempotency_key)
        self.tokens.append(token)
        status = self._statuses[0]
        body = {"id": f"order-{len(self.orders)}", "number": f"BC-{len(self.orders):010d}"}
        return ShopResponse(status, body if status < 300 else None)

    def request_payment(self, order_id, token, correlation_id):
        self.calls.append(("request_payment", order_id))
        return ShopResponse(self._statuses[1])

    def confirm_payment(self, order_id, method, token, correlation_id):
        self.calls.append(("confirm_payment", order_id))
        self.methods.append(method)
        return ShopResponse(self._statuses[2])

    def lookup_order(self, order_number, email, correlation_id):
        self.calls.append(("lookup_order", email))
        return ShopResponse(200)

    def my_orders(self, token, correlation_id):
        self.calls.append(("my_orders", token))
        return ShopResponse(200, {"items": []})

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]


class FakeAccountPool:
    """Comptes prêtés un par un, comme le vrai groupe."""

    def __init__(self, accounts: list[Account] | None = None) -> None:
        self.available = list(accounts or [])
        self.released: list[Account] = []

    def add(self, account: Account) -> None:
        self.available.append(account)

    def acquire(self, rng: Random) -> Account | None:
        return self.available.pop(0) if self.available else None

    def release(self, account: Account) -> None:
        self.released.append(account)
        self.available.append(account)


class FakeJourney:
    """Parcours de remplacement : compte les exécutions."""

    def __init__(self) -> None:
        self.runs = 0

    def execute(self, report, rng) -> None:
        self.runs += 1
        report.end_session()
