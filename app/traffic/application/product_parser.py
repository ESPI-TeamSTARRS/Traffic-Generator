from collections.abc import Mapping
from typing import Any

from app.traffic.domain.entities.product_ref import ProductRef


class ProductParser:
    """Extrait les produits d'une réponse GET /products ; tout élément mal formé est ignoré."""

    def parse(self, body: Mapping[str, Any] | None) -> list[ProductRef]:
        items = body.get("items") if body else None
        if not isinstance(items, list):
            return []
        return [ref for ref in map(self._to_ref, items) if ref is not None]

    def _to_ref(self, item: object) -> ProductRef | None:
        if not isinstance(item, dict):
            return None
        product_id, slug = item.get("id"), item.get("slug")
        if isinstance(product_id, str) and product_id and isinstance(slug, str) and slug:
            return ProductRef(id=product_id, slug=slug)
        return None
