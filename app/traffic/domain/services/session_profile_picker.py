from collections.abc import Sequence
from random import Random

from app.traffic.domain.value_objects.session_profile import SessionProfile


class SessionProfilePicker:
    """Tire le type de visiteur d'une session selon le poids de chaque profil."""

    def __init__(self, profiles: Sequence[SessionProfile]) -> None:
        if not profiles:
            raise ValueError("at least one profile is required")
        self._profiles = tuple(profiles)
        self._weights = [profile.weight for profile in profiles]

    def pick(self, rng: Random) -> SessionProfile:
        return rng.choices(self._profiles, weights=self._weights)[0]
