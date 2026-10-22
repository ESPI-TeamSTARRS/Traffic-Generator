"""Point d'entrée : uv run poe normal --minutes 60 --sessions-per-minute 15 --day-minutes 30"""

import argparse
from collections.abc import Sequence
from random import Random

import httpx

from app.core.settings import Settings
from app.traffic.application.browse_shop import BrowseShop
from app.traffic.application.customer_session import CustomerSession
from app.traffic.application.journey_mix import JourneyMix
from app.traffic.application.new_customer_journey import NewCustomerJourney
from app.traffic.application.order_flow import OrderFlow
from app.traffic.application.returning_customer_journey import ReturningCustomerJourney
from app.traffic.application.run_traffic import RunTraffic
from app.traffic.domain.entities.traffic_report import TrafficReport
from app.traffic.domain.interfaces.journey import Journey
from app.traffic.domain.services.account_factory import AccountFactory
from app.traffic.domain.services.address_book import AddressBook
from app.traffic.domain.services.burst_planner import BurstPlanner
from app.traffic.domain.services.default_session_profiles import DEFAULT_SESSION_PROFILES
from app.traffic.domain.services.load_profile import LoadProfile
from app.traffic.domain.services.popularity_policy import PopularityPolicy
from app.traffic.domain.services.session_profile_picker import SessionProfilePicker
from app.traffic.domain.services.think_time_policy import ThinkTimePolicy
from app.traffic.domain.services.token_bucket import TokenBucket
from app.traffic.infrastructure.httpx_auth_gateway import HttpxAuthGateway
from app.traffic.infrastructure.httpx_order_gateway import HttpxOrderGateway
from app.traffic.infrastructure.httpx_requester import build_client
from app.traffic.infrastructure.httpx_shop_gateway import HttpxShopGateway
from app.traffic.infrastructure.in_memory_account_pool import InMemoryAccountPool
from app.traffic.infrastructure.system_timer import SystemTimer
from app.traffic.infrastructure.thread_spawner import ThreadSpawner

SECONDS_PER_MINUTE = 60
MEAN_THINK_TIME_SECONDS = 2.0
LONG_PAUSE_PROBABILITY, LONG_PAUSE_MEAN_SECONDS = 0.08, 20.0  # lecture d'une fiche, café, onglet oublié
# Limites du générateur, un peu SOUS celles de la passerelle (par IP) pour ne jamais provoquer de 429 :
# register / verify-email / login : 60 par minute, rafale 30 ; tout /api/shop/orders* : 10 par minute, rafale 5.
AUTH_PER_MINUTE, AUTH_BURST = 40, 20
ORDER_PER_MINUTE, ORDER_BURST = 8, 4
NEW_CUSTOMER_SHARE = 0.3  # parmi les clients : 30 % de nouveaux inscrits, 70 % de clients qui se reconnectent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Générateur de trafic NORMAL vers la boutique Basecamp.")
    parser.add_argument("--minutes", type=float, default=1.0, help="durée de l'exécution (défaut : 1)")
    parser.add_argument(
        "--sessions-per-minute",
        type=float,
        default=6.0,
        help="visiteurs par minute, au pic si --day-minutes est utilisé (défaut : 6)",
    )
    parser.add_argument(
        "--day-minutes",
        type=float,
        default=None,
        help="durée d'un « jour » simulé en minutes : le trafic oscille entre nuit calme et pic",
    )
    parser.add_argument(
        "--night-factor",
        type=float,
        default=0.15,
        help="trafic de nuit en proportion du pic, entre 0 et 1 (défaut : 0.15)",
    )
    parser.add_argument(
        "--refusal-rate",
        type=float,
        default=0.03,
        help="part des sessions avec un refus normal, un produit introuvable (défaut : 0.03)",
    )
    parser.add_argument(
        "--customers",
        type=float,
        default=0.25,
        help="part des sessions avec un compte : inscription, connexion, commande (défaut : 0.25)",
    )
    parser.add_argument(
        "--typo-rate",
        type=float,
        default=0.1,
        help="part des connexions précédées d'une faute de mot de passe (défaut : 0.1)",
    )
    parser.add_argument(
        "--order-rate",
        type=float,
        default=0.12,
        help="part des clients connectés qui commandent (défaut : 0.12, ~3 %% de conversion)",
    )
    parser.add_argument(
        "--abandon-rate",
        type=float,
        default=0.25,
        help="part des commandes jamais payées, qui expirent (défaut : 0.25)",
    )
    parser.add_argument(
        "--slip-rate",
        type=float,
        default=0.03,
        help="part des gestes maladroits : saisie ou devis invalide, double clic (défaut : 0.03)",
    )
    parser.add_argument(
        "--bursts-per-hour",
        type=float,
        default=3.0,
        help="rafales de visiteurs légitimes par heure, ×2 à ×3,5 pendant 1 à 2,5 min (défaut : 3)",
    )
    parser.add_argument(
        "--decline-rate",
        type=float,
        default=0.1,
        help="part des paiements refusés par la méthode de test (défaut : 0.1)",
    )
    parser.add_argument("--seed", type=int, default=None, help="graine aléatoire pour rejouer le même trafic")
    return parser


def build_journey(args: argparse.Namespace, client: httpx.Client, timer: SystemTimer) -> Journey:
    """Assemble les parcours : invité seul, ou invité + nouveaux clients + clients qui se reconnectent."""
    think_time = ThinkTimePolicy(MEAN_THINK_TIME_SECONDS, LONG_PAUSE_PROBABILITY, LONG_PAUSE_MEAN_SECONDS)
    popularity = PopularityPolicy()
    guest = BrowseShop(
        HttpxShopGateway(client),
        timer,
        think_time,
        SessionProfilePicker(DEFAULT_SESSION_PROFILES),
        refusal_probability=args.refusal_rate,
        popularity=popularity,
        slip_probability=args.slip_rate,
    )
    if args.customers <= 0:
        return guest
    auth, orders, pool = HttpxAuthGateway(client), HttpxOrderGateway(client), InMemoryAccountPool()
    auth_limiter = TokenBucket(timer, AUTH_PER_MINUTE, AUTH_BURST)
    order_flow = OrderFlow(
        orders,
        timer,
        think_time,
        AddressBook(),
        TokenBucket(timer, ORDER_PER_MINUTE, ORDER_BURST),
        args.order_rate,
        args.decline_rate,
        args.abandon_rate,
        args.slip_rate,
        popularity,
    )
    session = CustomerSession(auth, orders, guest, order_flow)
    new = NewCustomerJourney(
        auth, pool, auth_limiter, AccountFactory(), session, guest, timer, think_time, args.slip_rate
    )
    returning = ReturningCustomerJourney(
        auth, pool, auth_limiter, session, new, timer, think_time, args.typo_rate, args.slip_rate
    )
    mix: list[tuple[float, Journey]] = [
        (1 - args.customers, guest),
        (args.customers * NEW_CUSTOMER_SHARE, new),
        (args.customers * (1 - NEW_CUSTOMER_SHARE), returning),
    ]
    return JourneyMix([(weight, journey) for weight, journey in mix if weight > 0])


def format_report(report: TrafficReport) -> str:
    statuses = ", ".join(f"{code or 'erreur réseau'}: {count}" for code, count in sorted(report.statuses.items()))
    return f"{report.sessions} sessions, {report.requests} requêtes ({statuses})"


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    rng = Random(args.seed)
    day_seconds = args.day_minutes * SECONDS_PER_MINUTE if args.day_minutes else None
    duration_seconds = args.minutes * SECONDS_PER_MINUTE
    bursts = BurstPlanner(args.bursts_per_hour).plan(rng, duration_seconds)
    timer = SystemTimer()
    with build_client(settings.base_url, settings.timeout_seconds) as client:
        run = RunTraffic(
            build_journey(args, client, timer),
            timer,
            rng,
            ThreadSpawner(),
            LoadProfile(day_seconds, args.night_factor, bursts),
        )
        print(
            f"Cible : {settings.base_url} ({args.minutes} min, {args.sessions_per_minute} sessions/min, "
            f"{len(bursts)} rafale(s) prévue(s))"
        )
        try:
            report = run.execute(duration_seconds, args.sessions_per_minute)
        except KeyboardInterrupt:
            print("Interrompu.")
            return 130
    print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
