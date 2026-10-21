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
uv run poe normal --minutes 60 --sessions-per-minute 15 --day-minutes 30   # 1 h avec 2 « jours » de 30 min
uv run poe normal --minutes 5 --seed 42                    # même graine = même trafic
```

| Option | Rôle | Défaut |
|---|---|---|
| `--minutes` | durée de l'exécution | 1 |
| `--sessions-per-minute` | visiteurs par minute (au pic si `--day-minutes` est utilisé) | 6 |
| `--day-minutes` | durée d'un « jour » simulé : le trafic passe de la nuit calme au pic de midi et redescend | désactivé |
| `--night-factor` | trafic de nuit en proportion du pic (0 à 1) | 0.15 |
| `--refusal-rate` | part des sessions avec un refus normal (produit introuvable, 404) | 0.03 |
| `--seed` | graine aléatoire pour rejouer le même trafic | aléatoire |

Autre cible (variable d'environnement, voir `.env.example`) :

```powershell
$env:TG_BASE_URL="http://127.0.0.1:8180"; uv run poe normal
```

Sortie type : `34 sessions, 144 requêtes (200: 143, 404: 1)`. Un code `erreur réseau` signifie que la pile ne répond pas.

## Ce que font les visiteurs

Chaque session tire un **profil** (poids relatifs) et des visiteurs arrivent **en parallèle** (jusqu'à 64 en même temps) :

| Profil | Poids | Comportement |
|---|---|---|
| curieux | 3 | 1 listing, 1 fiche, repart (2 requêtes) |
| flâneur | 4 | 2 listings (catégories différentes), 1 à 3 fiches, devis 1 fois sur 5 |
| acheteur | 2 | 1 listing, 2 à 5 fiches, devis 9 fois sur 10 |
| explorateur | 1 | 3 listings, 3 à 6 fiches, devis 1 fois sur 2 |

- Pauses irrégulières entre les actions (moyenne 2 s). Les fiches sont **lues dans le catalogue**, les devis ont 1 à 3 produits
  distincts, quantité 1 à 3.
- Une fois sur dix, `GET /api/shop/health`.
- Avec `--refusal-rate`, une session demande parfois un produit inexistant : le shop répond 404 et journalise
  `catalog.product_not_found` (outcome `denied`). C'est un refus **normal** (lien périmé) que le détecteur doit tolérer.
- Avec `--day-minutes`, le rythme d'arrivée suit un cycle jour/nuit comprimé (nuit au départ, pic à la moitié du jour).
- Chaque session envoie un même `X-Correlation-ID` (UUID v4, format accepté par le middleware Basecamp). Aucun prix n'est
  envoyé : le serveur seul décide. Ce trafic reste très en dessous de la limitation Traefik (10 requêtes/minute, seulement
  sur `/api/shop/orders*`).

## Architecture (calquée sur les services Basecamp)

Un projet `uv` autonome, tranche verticale `traffic`, un fichier = une classe, tests dans `__tests__/`.

```
app/
  core/settings.py                      configuration TG_*
  traffic/
    domain/          entities, enums, value_objects (CartLine, SessionProfile),
                     interfaces (ShopGateway, Timer, Spawner),
                     services (ThinkTimePolicy, SessionProfilePicker, LoadProfile, profils par défaut)
    application/     BrowseShop (une session), RunTraffic (arrivées, durée, rythme), ProductParser
    infrastructure/  HttpxShopGateway (HTTP vers /api/shop), SystemTimer, ThreadSpawner
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

- Trafic normal uniquement : pas de flood (à ajouter comme nouveau cas d'usage dans `application/`).
- Seules les routes exposées aujourd'hui sont utilisées : `shop` (catalogue, devis, santé). `auth` n'a pas de login et
  `payment` n'est pas routé par la passerelle ; les scénarios les couvrant viendront avec ces routes.
- Le seul refus produit est un produit introuvable (404). Les devis invalides ou les erreurs 5xx ne sont pas simulés.
- Pas de rafales aléatoires : les variations viennent des profils, de l'arrivée de Poisson, du parallélisme et du cycle jour/nuit.
- À lancer uniquement contre la pile locale du projet.
