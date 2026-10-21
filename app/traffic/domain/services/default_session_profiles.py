from app.traffic.domain.value_objects.session_profile import SessionProfile

# Mélange de visiteurs : beaucoup de curieux qui repartent vite, quelques acheteurs et explorateurs.
DEFAULT_SESSION_PROFILES = (
    SessionProfile("curieux", weight=3, listings=1, min_views=1, max_views=1, quote_probability=0.0),
    SessionProfile("flaneur", weight=4, listings=2, min_views=1, max_views=3, quote_probability=0.2),
    SessionProfile("acheteur", weight=2, listings=1, min_views=2, max_views=5, quote_probability=0.9),
    SessionProfile("explorateur", weight=1, listings=3, min_views=3, max_views=6, quote_probability=0.5),
)
