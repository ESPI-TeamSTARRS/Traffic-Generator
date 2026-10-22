from random import Random

from app.traffic.application.customer_session import CustomerSession
from app.traffic.application.token_parser import TokenParser
from app.traffic.domain.entities.traffic_report import TrafficReport
from app.traffic.domain.enums.registration_slip import RegistrationSlip
from app.traffic.domain.interfaces.account_pool import AccountPool
from app.traffic.domain.interfaces.auth_gateway import AuthGateway
from app.traffic.domain.interfaces.journey import Journey
from app.traffic.domain.interfaces.timer import Timer
from app.traffic.domain.services.account_factory import AccountFactory
from app.traffic.domain.services.correlation_id_factory import CorrelationIdFactory
from app.traffic.domain.services.think_time_policy import ThinkTimePolicy
from app.traffic.domain.services.token_bucket import TokenBucket
from app.traffic.domain.value_objects.account import Account

REGISTER_AND_LOGIN_COST = 2
DUPLICATE_REGISTRATION_SHARE = 0.5  # parmi les gestes maladroits : part des doubles clics sur « créer mon compte »


class NewCustomerJourney:
    """Un visiteur crée un compte, se connecte (l'email n'a pas besoin d'être vérifié) puis fait ses achats.

    Avec `slip_probability`, il se trompe parfois à l'inscription : mot de passe trop faible ou adresse invalide (422,
    puis il recommence correctement), ou double clic qui envoie deux fois la même inscription (le service répond 202
    dans les deux cas, sans révéler que le compte existe).
    Sans jeton de débit disponible, il se comporte comme un visiteur invité.
    Le compte créé rejoint le groupe des comptes réutilisables par les clients connus.
    """

    def __init__(
        self,
        auth: AuthGateway,
        pool: AccountPool,
        limiter: TokenBucket,
        factory: AccountFactory,
        session: CustomerSession,
        fallback: Journey,
        timer: Timer,
        think_time: ThinkTimePolicy,
        slip_probability: float = 0.0,
    ) -> None:
        if not 0 <= slip_probability <= 1:
            raise ValueError("slip_probability must be between 0 and 1")
        self._auth = auth
        self._pool = pool
        self._limiter = limiter
        self._factory = factory
        self._session = session
        self._fallback = fallback
        self._timer = timer
        self._think_time = think_time
        self._slip_probability = slip_probability
        self._ids = CorrelationIdFactory()
        self._parser = TokenParser()

    def execute(self, report: TrafficReport, rng: Random) -> None:
        slipping = rng.random() < self._slip_probability
        if not self._limiter.try_acquire(REGISTER_AND_LOGIN_COST + (1 if slipping else 0)):
            self._fallback.execute(report, rng)
            return
        correlation_id = self._ids.create(rng)
        duplicate = slipping and rng.random() < DUPLICATE_REGISTRATION_SHARE
        if slipping and not duplicate:
            self._failed_registration(correlation_id, report, rng)
        account = self._factory.create(rng)
        registered = self._auth.register(account, correlation_id)
        report.record(registered.status_code)
        if registered.is_success:
            if duplicate:
                report.record(self._auth.register(account, correlation_id).status_code)
            self._timer.sleep(self._think_time.sample(rng))
            self._log_in_and_shop(account, correlation_id, report, rng)
            self._pool.add(account)
        report.end_session()

    def _failed_registration(self, correlation_id: str, report: TrafficReport, rng: Random) -> None:
        slip = rng.choice(list(RegistrationSlip))
        report.record(self._auth.register(self._factory.create_flawed(rng, slip), correlation_id).status_code)
        self._timer.sleep(self._think_time.sample(rng))

    def _log_in_and_shop(self, account: Account, correlation_id: str, report: TrafficReport, rng: Random) -> None:
        login = self._auth.login(account, correlation_id)
        report.record(login.status_code)
        token = self._parser.access_token(login.body)
        if token:
            self._session.run(account.email, token, correlation_id, report, rng)
