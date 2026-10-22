import json
import threading
from random import Random

import httpx

from app.traffic.domain.enums.payment_method import PaymentMethod
from app.traffic.domain.value_objects.account import Account
from app.traffic.domain.value_objects.cart_line import CartLine
from app.traffic.domain.value_objects.order_request import OrderRequest
from app.traffic.domain.value_objects.shipping_address import ShippingAddress
from app.traffic.infrastructure.httpx_auth_gateway import HttpxAuthGateway
from app.traffic.infrastructure.httpx_order_gateway import HttpxOrderGateway
from app.traffic.infrastructure.httpx_requester import build_client
from app.traffic.infrastructure.in_memory_account_pool import InMemoryAccountPool

CID = "11111111-2222-4333-8444-555555555555"
ACCOUNT = Account("client-1@example.com", "Bivouac-00000000000000000001-Rando")
ORDER = OrderRequest(
    "client-1@example.com",
    ShippingAddress("Camille Martin", "12 rue des Alpes", "38000", "Grenoble", "FR"),
    (CartLine("p1", 1), CartLine("p2", 1)),
)


def client_recording(sent: list[httpx.Request], status: int = 200, body: object = None) -> httpx.Client:
    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(status, json=body if body is not None else {})

    return httpx.Client(base_url="http://gateway", transport=httpx.MockTransport(respond))


# --- auth ----------------------------------------------------------------------------

def test_register_and_login_post_the_credentials_under_api_auth() -> None:
    sent: list[httpx.Request] = []
    gateway = HttpxAuthGateway(client_recording(sent))
    gateway.register(ACCOUNT, CID)
    gateway.login(ACCOUNT, CID)
    assert [(r.method, r.url.path) for r in sent] == [("POST", "/api/auth/register"), ("POST", "/api/auth/login")]
    assert all(json.loads(r.content) == {"email": ACCOUNT.email, "password": ACCOUNT.password} for r in sent)
    assert all(r.headers["X-Correlation-ID"] == CID for r in sent)


def test_me_sends_the_bearer_token_and_no_body() -> None:
    sent: list[httpx.Request] = []
    HttpxAuthGateway(client_recording(sent)).me("jeton-abc", CID)
    assert sent[0].method == "GET" and sent[0].url.path == "/api/auth/me"
    assert sent[0].headers["Authorization"] == "Bearer jeton-abc" and not sent[0].content


def test_login_response_exposes_the_json_body() -> None:
    sent: list[httpx.Request] = []
    response = HttpxAuthGateway(client_recording(sent, 200, {"access_token": "t"})).login(ACCOUNT, CID)
    assert response.status_code == 200 and response.body == {"access_token": "t"}


# --- commandes -----------------------------------------------------------------------

def test_create_order_sends_the_documented_body_and_idempotency_key() -> None:
    sent: list[httpx.Request] = []
    HttpxOrderGateway(client_recording(sent, 201, {"id": "o1"})).create_order(ORDER, "tg-0123456789", "jeton-abc", CID)
    request = sent[0]
    assert (request.method, request.url.path) == ("POST", "/api/shop/orders")
    assert request.headers["Idempotency-Key"] == "tg-0123456789"
    assert request.headers["Authorization"] == "Bearer jeton-abc"
    assert json.loads(request.content) == {
        "email": "client-1@example.com",
        "shippingAddress": {"fullName": "Camille Martin", "line1": "12 rue des Alpes", "postalCode": "38000",
                            "city": "Grenoble", "country": "FR"},
        "lines": [{"productId": "p1", "quantity": 1}, {"productId": "p2", "quantity": 1}],
    }


def test_guest_order_has_no_authorization_header() -> None:
    sent: list[httpx.Request] = []
    HttpxOrderGateway(client_recording(sent)).create_order(ORDER, "tg-0123456789", None, CID)
    assert "Authorization" not in sent[0].headers


def test_payment_request_and_confirmation_paths_and_body() -> None:
    sent: list[httpx.Request] = []
    gateway = HttpxOrderGateway(client_recording(sent))
    gateway.request_payment("o1", "jeton-abc", CID)
    gateway.confirm_payment("o1", PaymentMethod.DECLINED, "jeton-abc", CID)
    assert [(r.method, r.url.path) for r in sent] == [("POST", "/api/shop/orders/o1/pay"),
                                                       ("POST", "/api/shop/orders/o1/pay/confirm")]
    assert not sent[0].content and json.loads(sent[1].content) == {"payment_method": "pm_test_declined"}


def test_my_orders_needs_the_token() -> None:
    sent: list[httpx.Request] = []
    HttpxOrderGateway(client_recording(sent)).my_orders("jeton-abc", CID)
    assert sent[0].url.path == "/api/shop/me/orders" and sent[0].headers["Authorization"] == "Bearer jeton-abc"


# --- client sans cookies ---------------------------------------------------------------

def test_client_never_keeps_cookies_between_visitors() -> None:
    seen: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, headers={"Set-Cookie": "refresh_token=secret; Path=/api/auth"}, json={})

    client = build_client("http://127.0.0.1:8080", 5.0)
    client._transport = httpx.MockTransport(respond)  # remplace le réseau, garde la politique de cookies
    client.get("http://127.0.0.1:8080/api/auth/health")
    client.get("http://127.0.0.1:8080/api/auth/health")
    assert len(seen) == 2 and all("Cookie" not in r.headers for r in seen)


# --- groupe de comptes -----------------------------------------------------------------

def test_pool_lends_each_account_to_one_visitor_at_a_time() -> None:
    pool, rng = InMemoryAccountPool(), Random(1)
    assert pool.acquire(rng) is None
    pool.add(ACCOUNT)
    assert pool.acquire(rng) == ACCOUNT
    assert pool.acquire(rng) is None          # prêté : plus disponible
    pool.release(ACCOUNT)
    assert pool.acquire(rng) == ACCOUNT


def test_pool_is_safe_under_concurrency() -> None:
    pool = InMemoryAccountPool()
    accounts = [Account(f"c{i}@example.com", f"pw-{i:020d}-long") for i in range(200)]
    threads = [threading.Thread(target=pool.add, args=(a,)) for a in accounts]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    taken: list[Account] = []
    lock = threading.Lock()

    def take() -> None:
        got = pool.acquire(Random())
        with lock:
            taken.append(got)

    takers = [threading.Thread(target=take) for _ in range(200)]
    for t in takers:
        t.start()
    for t in takers:
        t.join()
    assert len(taken) == 200 and None not in taken and len({a.email for a in taken}) == 200


# --- gestes maladroits -------------------------------------------------------------------

def test_bad_query_listing_uses_an_unknown_category() -> None:
    from app.traffic.infrastructure.httpx_shop_gateway import HttpxShopGateway

    sent: list[httpx.Request] = []
    HttpxShopGateway(client_recording(sent)).list_products_with_bad_query(CID)
    assert sent[0].url.path == "/api/shop/products" and sent[0].url.params["category"] == "categorie-inconnue"


def test_order_lookup_posts_number_and_email_without_token() -> None:
    sent: list[httpx.Request] = []
    HttpxOrderGateway(client_recording(sent)).lookup_order("BC-ABCDEFGHIJ", "client-1@example.com", CID)
    assert (sent[0].method, sent[0].url.path) == ("POST", "/api/shop/orders/lookup")
    assert json.loads(sent[0].content) == {"orderNumber": "BC-ABCDEFGHIJ", "email": "client-1@example.com"}
    assert "Authorization" not in sent[0].headers
