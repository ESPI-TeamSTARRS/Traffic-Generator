from app.traffic.application.product_parser import ProductParser
from app.traffic.domain.entities.product_ref import ProductRef


def test_extracts_id_and_slug() -> None:
    body = {"items": [{"id": "p1", "slug": "tente-a", "name": "x"}]}
    assert ProductParser().parse(body) == [ProductRef("p1", "tente-a")]


def test_ignores_malformed_items() -> None:
    bad = [{"id": "p1"}, "texte", {"id": 3, "slug": "s"}, {"id": "", "slug": "s"}]
    body = {"items": [*bad, {"id": "ok", "slug": "s"}]}
    assert ProductParser().parse(body) == [ProductRef("ok", "s")]


def test_missing_or_invalid_body_gives_nothing() -> None:
    assert ProductParser().parse(None) == []
    assert ProductParser().parse({}) == []
    assert ProductParser().parse({"items": "x"}) == []
