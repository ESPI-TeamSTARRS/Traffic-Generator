"""Point d'entrée : uv run poe normal --minutes 5 --sessions-per-minute 6"""
import argparse
from collections.abc import Sequence
from random import Random

import httpx

from app.core.settings import Settings
from app.traffic.application.browse_shop import BrowseShop
from app.traffic.application.run_traffic import RunTraffic
from app.traffic.domain.entities.traffic_report import TrafficReport
from app.traffic.domain.services.think_time_policy import ThinkTimePolicy
from app.traffic.infrastructure.httpx_shop_gateway import HttpxShopGateway
from app.traffic.infrastructure.system_timer import SystemTimer

SECONDS_PER_MINUTE = 60
MEAN_THINK_TIME_SECONDS = 2.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Générateur de trafic NORMAL vers la boutique Basecamp.")
    parser.add_argument("--minutes", type=float, default=1.0, help="durée de l'exécution (défaut : 1)")
    parser.add_argument("--sessions-per-minute", type=float, default=6.0, help="visiteurs par minute (défaut : 6)")
    parser.add_argument("--seed", type=int, default=None, help="graine aléatoire pour rejouer le même trafic")
    return parser


def format_report(report: TrafficReport) -> str:
    statuses = ", ".join(f"{code or 'erreur réseau'}: {count}" for code, count in sorted(report.statuses.items()))
    return f"{report.sessions} sessions, {report.requests} requêtes ({statuses})"


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    rng = Random(args.seed)
    with httpx.Client(base_url=settings.base_url, timeout=settings.timeout_seconds) as client:
        timer = SystemTimer()
        browse = BrowseShop(HttpxShopGateway(client), timer, ThinkTimePolicy(MEAN_THINK_TIME_SECONDS), rng)
        print(f"Cible : {settings.base_url} ({args.minutes} min, {args.sessions_per_minute} sessions/min)")
        try:
            report = RunTraffic(browse, timer, rng).execute(args.minutes * SECONDS_PER_MINUTE, args.sessions_per_minute)
        except KeyboardInterrupt:
            print("Interrompu.")
            return 130
    print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
