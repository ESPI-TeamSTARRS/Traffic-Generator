from random import Random
from uuid import UUID


class CorrelationIdFactory:
    """Identifiant de session (UUID v4 tiré du générateur : rejouable) au format accepté par le middleware Basecamp."""

    def create(self, rng: Random) -> str:
        return str(UUID(int=rng.getrandbits(128), version=4))
