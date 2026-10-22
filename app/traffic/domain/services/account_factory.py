from random import Random

from app.traffic.domain.enums.registration_slip import RegistrationSlip
from app.traffic.domain.value_objects.account import Account

EMAIL_DOMAIN = "example.com"  # domaine réservé à la documentation : aucun vrai destinataire


class AccountFactory:
    """Fabrique des identifiants jetables : email unique et mot de passe long qui respecte la politique d'auth."""

    def create(self, rng: Random) -> Account:
        email = f"client-{rng.getrandbits(48):012x}@{EMAIL_DOMAIN}"
        password = f"Bivouac-{rng.getrandbits(80):020x}-Rando"  # 12 à 128 caractères, absent des mots de passe courants
        return Account(email, password)

    def create_flawed(self, rng: Random, slip: RegistrationSlip) -> Account:
        """Une saisie ratée : mot de passe trop court (et courant) ou adresse qui n'en est pas une."""
        account = self.create(rng)
        if slip is RegistrationSlip.TOO_SHORT:
            return Account(account.email, "azerty")
        return Account("pas-une-adresse", account.password)
