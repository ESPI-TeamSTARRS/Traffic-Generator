from random import Random

from app.traffic.application.customer_session import CustomerSession
from app.traffic.application.token_parser import TokenParser
from app.traffic.domain.entities.traffic_report import TrafficReport
from app.traffic.domain.interfaces.account_pool import AccountPool
from app.traffic.domain.interfaces.auth_gateway import AuthGateway
from app.traffic.domain.interfaces.journey import Journey
from app.traffic.domain.interfaces.timer import Timer
from app.traffic.domain.services.correlation_id_factory import CorrelationIdFactory
from app.traffic.domain.services.think_time_policy import ThinkTimePolicy
from app.traffic.domain.services.token_bucket import TokenBucket
from app.traffic.domain.value_objects.account import Account


class ReturningCustomerJourney:
    """Un client déjà inscrit se reconnecte, parfois après une erreur de saisie.

    L'erreur est soit une faute dans le mot de passe (`typo_probability`), soit une faute dans l'adresse
    (`unknown_email_probability` : adresse inconnue, toujours différente). Une seule erreur par visite, toujours suivie
    de la bonne connexion : le compteur de verrouillage d'auth (5 échecs en 15 minutes) repart à zéro à chaque connexion
    réussie et ne se déclenche jamais. Un compte n'est prêté qu'à un visiteur à la fois, pour que deux visites
    simultanées n'additionnent pas leurs échecs.
    Sans compte disponible ou sans jeton de débit, il se comporte comme un nouveau client (puis comme un invité).
    """

    def __init__(
        self,
        auth: AuthGateway,
        pool: AccountPool,
        limiter: TokenBucket,
        session: CustomerSession,
        fallback: Journey,
        timer: Timer,
        think_time: ThinkTimePolicy,
        typo_probability: float,
        unknown_email_probability: float = 0.0,
    ) -> None:
        for name, value in (("typo_probability", typo_probability),
                            ("unknown_email_probability", unknown_email_probability)):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        self._auth = auth
        self._pool = pool
        self._limiter = limiter
        self._session = session
        self._fallback = fallback
        self._timer = timer
        self._think_time = think_time
        self._typo_probability = typo_probability
        self._unknown_email_probability = unknown_email_probability
        self._ids = CorrelationIdFactory()
        self._parser = TokenParser()

    def execute(self, report: TrafficReport, rng: Random) -> None:
        account = self._pool.acquire(rng)
        if account is None:
            self._fallback.execute(report, rng)
            return
        failed_attempt = self._failed_attempt(account, rng)
        if not self._limiter.try_acquire(2 if failed_attempt else 1):
            self._pool.release(account)
            self._fallback.execute(report, rng)
            return
        try:
            self._visit(account, failed_attempt, report, rng)
        finally:
            self._pool.release(account)
        report.end_session()

    def _failed_attempt(self, account: Account, rng: Random) -> Account | None:
        """Les identifiants de l'essai raté de cette visite (ou None s'il n'y en a pas)."""
        if rng.random() < self._typo_probability:
            return account.mistyped()
        if rng.random() < self._unknown_email_probability:
            return account.with_unknown_email(rng)
        return None

    def _visit(self, account: Account, failed_attempt: Account | None, report: TrafficReport, rng: Random) -> None:
        correlation_id = self._ids.create(rng)
        if failed_attempt is not None:
            report.record(self._auth.login(failed_attempt, correlation_id).status_code)
            self._timer.sleep(self._think_time.sample(rng))
        login = self._auth.login(account, correlation_id)
        report.record(login.status_code)
        token = self._parser.access_token(login.body)
        if token:
            self._session.run(account.email, token, correlation_id, report, rng)
