from collections import Counter

import httpx
import pytest

from app.core.settings import Settings
from app.traffic.domain.entities.traffic_report import TrafficReport
from app.traffic.presentation import cli


def test_parser_defaults_and_options() -> None:
    args = cli.build_parser().parse_args(
        ["--minutes", "5", "--sessions-per-minute", "10", "--seed", "3", "--day-minutes", "30", "--refusal-rate", "0.1"]
    )
    assert (args.minutes, args.sessions_per_minute, args.seed) == (5.0, 10.0, 3)
    assert (args.day_minutes, args.refusal_rate, args.night_factor) == (30.0, 0.1, 0.15)
    defaults = cli.build_parser().parse_args([])
    assert (defaults.customers, defaults.typo_rate) == (0.25, 0.1)
    assert (defaults.order_rate, defaults.decline_rate) == (0.12, 0.1)
    assert (defaults.abandon_rate, defaults.slip_rate, defaults.bursts_per_hour) == (0.25, 0.03, 3.0)


def test_format_report_names_network_errors() -> None:
    report = TrafficReport()
    report.statuses = Counter({200: 3, 0: 1})
    report.sessions = 2
    assert cli.format_report(report) == "2 sessions, 4 requêtes (erreur réseau: 1, 200: 3)"


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TG_BASE_URL", "http://example.test:9000/")
    monkeypatch.setenv("TG_TIMEOUT_SECONDS", "2.5")
    assert Settings.from_env() == Settings(base_url="http://example.test:9000", timeout_seconds=2.5)


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TG_BASE_URL", raising=False)
    monkeypatch.delenv("TG_TIMEOUT_SECONDS", raising=False)
    assert Settings.from_env().base_url == "http://127.0.0.1:8080"


def test_main_runs_against_an_unreachable_stack_without_crashing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TG_BASE_URL", "http://127.0.0.1:1")  # port fermé : erreurs réseau comptées, pas de crash
    monkeypatch.setattr(cli.SystemTimer, "sleep", lambda self, seconds: None)
    ticks = iter(range(0, 10_000))
    monkeypatch.setattr(cli.SystemTimer, "now", lambda self: next(ticks) * 10.0)
    assert cli.main(["--minutes", "1", "--sessions-per-minute", "6", "--seed", "1"]) == 0
    assert "erreur réseau" in capsys.readouterr().out


def test_httpx_is_the_http_client() -> None:
    assert cli.httpx is httpx
