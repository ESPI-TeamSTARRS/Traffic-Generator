import json

import httpx

from app.traffic.domain.entities.shop_response import TRANSPORT_ERROR
from app.traffic.domain.enums.product_category import ProductCategory
from app.traffic.domain.value_objects.cart_line import CartLine
from app.traffic.infrastructure.httpx_shop_gateway import HttpxShopGateway

CID = "11111111-2222-4333-8444-555555555555"


def gateway_with(handler: httpx.MockTransport | None = None, requests: list[httpx.Request] | None = None):
    def respond(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        return httpx.Response(200, json={"items": []})

    transport = handler or httpx.MockTransport(respond)
    return HttpxShopGateway(httpx.Client(base_url="http://gateway", transport=transport))


def test_list_products_uses_gateway_prefix_filters_and_correlation_header() -> None:
    sent: list[httpx.Request] = []
    gateway_with(requests=sent).list_products(ProductCategory.TENTS, 2, 12, CID)
    request = sent[0]
    assert (request.method, request.url.path) == ("GET", "/api/shop/products")
    assert dict(request.url.params) == {"category": "tentes", "page": "2", "page_size": "12"}
    assert request.headers["X-Correlation-ID"] == CID


def test_list_products_without_category_omits_the_filter() -> None:
    sent: list[httpx.Request] = []
    gateway_with(requests=sent).list_products(None, 1, 12, CID)
    assert "category" not in sent[0].url.params


def test_get_product_and_health_paths() -> None:
    sent: list[httpx.Request] = []
    gateway = gateway_with(requests=sent)
    gateway.get_product("tente-a", CID)
    gateway.health(CID)
    assert [r.url.path for r in sent] == ["/api/shop/products/tente-a", "/api/shop/health"]


def test_quote_cart_sends_only_product_id_and_quantity() -> None:
    sent: list[httpx.Request] = []
    gateway_with(requests=sent).quote_cart([CartLine("p1", 2), CartLine("p2", 1)], CID)
    assert sent[0].method == "POST"
    assert json.loads(sent[0].content) == {
        "lines": [{"productId": "p1", "quantity": 2}, {"productId": "p2", "quantity": 1}]
    }


def test_response_carries_status_and_json_object() -> None:
    response = gateway_with().health(CID)
    assert response.status_code == 200 and response.body == {"items": []}


def test_non_json_or_non_object_body_gives_no_body() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(502, text="<html>"))
    assert gateway_with(transport).health(CID).body is None
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=[1, 2]))
    assert gateway_with(transport).health(CID).body is None


def test_network_error_becomes_transport_error_status() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    response = gateway_with(httpx.MockTransport(fail)).health(CID)
    assert response.status_code == TRANSPORT_ERROR and not response.is_success
