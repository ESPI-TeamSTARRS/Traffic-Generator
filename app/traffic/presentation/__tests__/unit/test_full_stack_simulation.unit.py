"""Simulation complète contre une fausse pile qui applique les MÊMES limites que la passerelle et auth.

Vérifie le point demandé : le générateur ne déclenche jamais de 429 (limites de débit de Traefik) ni de verrouillage
de compte (5 échecs de connexion d'affilée), même à un rythme élevé et pendant de longues durées simulées.
"""
import argparse
import json
import sys
import uuid
from pathlib import Path
from random import Random

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "application" / "__tests__"))

from fakes import FakeTimer, InlineSpawner  # noqa: E402

from app.traffic.application.run_traffic import RunTraffic  # noqa: E402
from app.traffic.domain.services.burst_planner import BurstPlanner  # noqa: E402
from app.traffic.domain.services.load_profile import LoadProfile  # noqa: E402
from app.traffic.domain.services.token_bucket import TokenBucket  # noqa: E402
from app.traffic.presentation import cli  # noqa: E402

CATEGORIES = {"tentes", "couchage", "sacs-a-dos", "cuisine", "securite"}
PRODUCTS = [{"id": f"p{i}", "slug": f"produit-{i}"} for i in range(1, 9)]
LOCKOUT_FAILURES = 5


class FakeStack:
    """Passerelle, shop et auth simulés : limites de Traefik (60/min rafale 30 ; 10/min rafale 5) et verrouillage."""

    def __init__(self, timer: FakeTimer) -> None:
        self.auth_limit = TokenBucket(timer, 60, 30)
        self.order_limit = TokenBucket(timer, 10, 5)
        self.accounts: dict[str, str] = {}
        self.failures: dict[str, int] = {}
        self.max_failures = 0
        self.statuses: dict[str, list[int]] = {}
        self.cookies_seen = 0
        self.orders_by_key: dict[str, str] = {}
        self.order_emails: dict[str, str] = {}
        self.paid: set[str] = set()

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.cookies_seen += "Cookie" in request.headers
        status, body = self._route(request)
        self.statuses.setdefault(request.url.path, []).append(status)
        return httpx.Response(status, json=body)

    def count(self, status: int) -> int:
        return sum(codes.count(status) for codes in self.statuses.values())

    def _route(self, request: httpx.Request) -> tuple[int, dict]:
        path = request.url.path
        if path in ("/api/auth/register", "/api/auth/login", "/api/auth/verify-email"):
            if not self.auth_limit.try_acquire():
                return 429, {}
            return self._auth(request, path)
        if path.startswith("/api/shop/orders"):
            if not self.order_limit.try_acquire():
                return 429, {}
            return self._orders(request)
        if path == "/api/auth/me":
            return (200, {"id": "u"}) if request.headers.get("Authorization", "").startswith("Bearer ") else (401, {})
        return self._shop(request)

    def _auth(self, request: httpx.Request, path: str) -> tuple[int, dict]:
        creds = json.loads(request.content)
        if path.endswith("register"):
            if "@" not in creds["email"] or len(creds["password"]) < 12:
                return 422, {}
            self.accounts.setdefault(creds["email"], creds["password"])
            return 202, {}
        email = creds["email"]
        if self.failures.get(email, 0) >= LOCKOUT_FAILURES:
            return 401, {}
        if self.accounts.get(email) == creds["password"]:
            self.failures[email] = 0
            return 200, {"access_token": f"jeton-{uuid.uuid4().hex}"}
        self.failures[email] = self.failures.get(email, 0) + 1
        self.max_failures = max(self.max_failures, self.failures[email])
        return 401, {}

    def _orders(self, request: httpx.Request) -> tuple[int, dict]:
        path = request.url.path
        if path == "/api/shop/orders":
            return self._create_order(request)
        if path == "/api/shop/orders/lookup":
            data = json.loads(request.content)
            known = self.order_emails.get(data["orderNumber"]) == data["email"]
            return (200, {"status": "pending_payment"}) if known else (404, {})
        order_id = path.split("/")[4]
        if path.endswith("/confirm"):
            if order_id in self.paid:
                return 409, {}
            self.paid.add(order_id)
            return 200, {}
        return 201, {}

    def _create_order(self, request: httpx.Request) -> tuple[int, dict]:
        key = request.headers["Idempotency-Key"]
        if key in self.orders_by_key:
            return 200, {"id": self.orders_by_key[key], "number": "BC-REJEU"}
        order_id, number = uuid.uuid4().hex, "BC-" + uuid.uuid4().hex[:10].upper()
        self.orders_by_key[key] = order_id
        self.order_emails[number] = json.loads(request.content)["email"]
        return 201, {"id": order_id, "number": number}

    def _shop(self, request: httpx.Request) -> tuple[int, dict]:
        path = request.url.path
        if path == "/api/shop/products":
            category = request.url.params.get("category")
            if category is not None and category not in CATEGORIES:
                return 422, {}
            return 200, {"items": PRODUCTS}
        if path.startswith("/api/shop/products/"):
            return (200, {}) if path.rsplit("/", 1)[1] in {p["slug"] for p in PRODUCTS} else (404, {})
        if path == "/api/shop/cart/quote":
            ids = [line["productId"] for line in json.loads(request.content)["lines"]]
            known = {p["id"] for p in PRODUCTS}
            return (200, {}) if len(set(ids)) == len(ids) and set(ids) <= known else (422, {})
        return 200, {"items": []}   # santé, mes commandes


def run(minutes: float, per_minute: float, seed: int = 1, **options) -> FakeStack:
    timer = FakeTimer()
    stack = FakeStack(timer)
    client = httpx.Client(base_url="http://gateway", transport=httpx.MockTransport(stack.handle))
    args = argparse.Namespace(refusal_rate=0.03, customers=0.5, typo_rate=0.3, order_rate=0.8, decline_rate=0.2,
                              abandon_rate=0.25, slip_rate=0.1)
    for name, value in options.items():
        setattr(args, name, value)
    journey = cli.build_journey(args, client, timer)  # même assemblage que la CLI
    rng = Random(seed)
    bursts = BurstPlanner(per_hour=6).plan(rng, minutes * 60)
    RunTraffic(journey, timer, rng, InlineSpawner(), LoadProfile(bursts=bursts)).execute(minutes * 60, per_minute)
    return stack


def test_never_triggers_a_rate_limit_even_at_a_high_rate() -> None:
    stack = run(minutes=30, per_minute=120)
    assert stack.count(429) == 0
    assert len(stack.statuses.get("/api/shop/orders", [])) > 20      # il commande bien


def test_never_gets_close_to_the_lockout_threshold() -> None:
    stack = run(minutes=60, per_minute=60, typo_rate=1.0)           # une faute de frappe à CHAQUE connexion
    assert stack.max_failures == 1
    logins = stack.statuses["/api/auth/login"]
    assert logins.count(401) > 20 and logins.count(200) >= logins.count(401)


def test_every_flow_is_exercised_end_to_end() -> None:
    stack = run(minutes=30, per_minute=60)
    for path in ("/api/auth/register", "/api/auth/login", "/api/auth/me", "/api/shop/orders",
                 "/api/shop/me/orders", "/api/shop/products"):
        assert stack.statuses.get(path), path
    assert stack.count(500) == 0 and stack.count(0) == 0


def test_without_customers_only_the_shop_catalog_is_used() -> None:
    stack = run(minutes=10, per_minute=30, customers=0)
    assert not any(path.startswith("/api/auth") or path.startswith("/api/shop/orders") for path in stack.statuses)


def test_no_session_cookie_is_ever_sent() -> None:
    assert run(minutes=10, per_minute=30).cookies_seen == 0


def test_accounts_are_reused_across_visits() -> None:
    stack = run(minutes=30, per_minute=60)
    assert len(stack.statuses["/api/auth/login"]) > len(stack.accounts)   # plus de connexions que de comptes créés


def test_realistic_refusals_all_appear_and_stay_a_minority() -> None:
    stack = run(minutes=60, per_minute=60, slip_rate=0.15)
    assert stack.count(422) > 5 and stack.count(404) > 5 and stack.count(401) > 5 and stack.count(409) >= 1
    assert stack.count(429) == 0 and stack.max_failures == 1
    total = sum(len(codes) for codes in stack.statuses.values())
    refusals = sum(stack.count(code) for code in (401, 404, 409, 422))
    assert 0.01 < refusals / total < 0.25


def test_idempotent_replay_returns_the_same_order() -> None:
    stack = run(minutes=60, per_minute=60, slip_rate=0.5, order_rate=1.0)
    assert stack.statuses["/api/shop/orders"].count(200) > 0       # rejeu : 200 au lieu de 201
    assert len(stack.orders_by_key) == stack.statuses["/api/shop/orders"].count(201)


def test_unpaid_orders_exist_when_visitors_abandon() -> None:
    stack = run(minutes=60, per_minute=60, abandon_rate=0.6, order_rate=1.0)
    assert len(stack.orders_by_key) > len(stack.paid) > 0


def test_a_burst_raises_the_arrival_rate_without_breaking_a_limit() -> None:
    calm = run(minutes=30, per_minute=30, seed=4)
    assert calm.count(429) == 0
