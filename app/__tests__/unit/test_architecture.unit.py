"""Règle de dépendance (comme dans les services Basecamp) : domain <- application <- infrastructure/presentation."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = {
    "domain": ("app.traffic.application", "app.traffic.infrastructure", "app.traffic.presentation", "httpx"),
    "application": ("app.traffic.infrastructure", "app.traffic.presentation", "httpx"),
    "infrastructure": ("app.traffic.presentation", "app.traffic.application"),
}


def imports_of(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def violations(layer: str) -> list[str]:
    bad: list[str] = []
    for path in (ROOT / "traffic" / layer).rglob("*.py"):
        if "__tests__" in path.parts:
            continue
        for module in imports_of(path):
            if any(module == f or module.startswith(f + ".") for f in FORBIDDEN[layer]):
                bad.append(f"{path.relative_to(ROOT)} importe {module}")
    return bad


def test_domain_depends_on_nothing_outward() -> None:
    assert violations("domain") == []


def test_application_depends_only_on_domain() -> None:
    assert violations("application") == []


def test_infrastructure_does_not_depend_on_application_or_presentation() -> None:
    assert violations("infrastructure") == []
