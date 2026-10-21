# Traffic Generator : trafic normal pour la boutique Basecamp

Simule des visiteurs qui parcourent la boutique (catalogue, fiches produits, devis de panier) en passant par la
passerelle Traefik. Les services Basecamp produisent eux-mêmes leurs logs JSON (`docs/development/logging.md`) :
le détecteur ML apprend ensuite sur ce trafic « normal ». Ce générateur n'écrit aucun log lui-même.

## Prérequis

- [uv](https://docs.astral.sh/uv/)
- La pile Basecamp lancée (`docker compose up` dans `BaseCamp/`), passerelle sur `http://127.0.0.1:8080`.

## Utilisation (Windows / PowerShell)

```powershell
uv sync
uv run poe normal                                          # 1 minute, 6 visiteurs/minute
uv run poe normal --minutes 60 --sessions-per-minute 6     # une heure de trafic d'entraînement
uv run poe normal --minutes 5 --seed 42                    # même graine = même trafic
```

Autre cible (variables d'environnement, voir `.env.example`) :

```powershell
$env:TG_BASE_URL="http://127.0.0.1:8080"; uv run poe normal
```

Sortie type : `12 sessions, 41 requêtes (200: 41)`. Un code `erreur réseau` signifie que la pile ne répond pas.

## Ce que fait un visiteur

1. `GET /api/shop/products` (catégorie au hasard ou aucune, 12 produits).
2. 1 à 3 fois `GET /api/shop/products/{slug}` sur des produits **lus dans le catalogue**, avec des pauses irrégulières (moyenne 2 s).
3. Une fois sur deux, `POST /api/shop/cart/quote` avec 1 à 3 produits distincts, quantité 1 à 3.
4. Une fois sur dix, `GET /api/shop/health`.

Chaque session envoie un même `X-Correlation-ID` (UUID v4, format accepté par le middleware Basecamp). Aucun prix n'est
envoyé : le serveur seul décide. Le rythme `--sessions-per-minute` est un rythme moyen entre débuts de sessions.
Ce trafic reste très en dessous de la limitation Traefik (10 requêtes/minute, seulement sur `/api/shop/orders*`).

## Architecture (calquée sur les services Basecamp)

Un projet `uv` autonome, tranche verticale `traffic`, un fichier = une classe, tests dans `__tests__/`.

```
app/
  core/settings.py                      configuration TG_*
  traffic/
    domain/          entities, enums, value_objects, interfaces (ShopGateway, Timer), services (ThinkTimePolicy)
    application/     BrowseShop (une session), RunTraffic (la durée et le rythme), ProductParser
    infrastructure/  HttpxShopGateway (HTTP vers /api/shop), SystemTimer
    presentation/    cli.py (point d'entrée et assemblage)
```

Règle de dépendance vérifiée par `app/__tests__/unit/test_architecture.unit.py` : `domain` n'importe rien d'extérieur,
`application` seulement `domain`, `infrastructure` ni `application` ni `presentation`.

## Développement

```powershell
uv run poe check    # ruff + tests (couverture minimale 80 %)
uv run poe test
uv run poe lint
uv run poe format
```

## Limites

- Trafic normal uniquement : pas de flood ni de requêtes invalides (à ajouter comme nouveaux cas d'usage dans `application/`).
- Seules les routes exposées aujourd'hui sont utilisées : `shop` (catalogue, devis, santé). `auth` n'a pas de login et
  `payment` n'est pas routé par la passerelle ; les scénarios les couvrant viendront avec ces routes.
- À lancer uniquement contre la pile locale du projet.
