from dataclasses import dataclass
from random import Random


@dataclass(frozen=True)
class Account:
    """Compte client fictif créé par le générateur (identifiants jetables, jamais affichés ni écrits sur disque)."""

    email: str
    password: str

    def mistyped(self) -> "Account":
        """Le même compte avec une faute de frappe dans le mot de passe : un échec de connexion normal."""
        return Account(self.email, self.password + "x")

    def with_unknown_email(self, rng: Random) -> "Account":
        """Même mot de passe, adresse inconnue d'auth (faute de frappe). Chaque adresse est unique : le verrouillage
        d'auth est clé sur l'adresse, des essais répétés sur la même fausse adresse finiraient par la verrouiller."""
        local, _, domain = self.email.partition("@")
        return Account(f"{local}-{rng.getrandbits(32):08x}@{domain}", self.password)
