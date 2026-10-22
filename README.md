# Traffic Generator : trafic normal pour la boutique Basecamp

Simule des visiteurs qui parcourent la boutique (catalogue, fiches produits, devis de panier), créent un compte, se
connectent, commandent et paient, en passant par la passerelle Traefik. Les services Basecamp produisent eux-mêmes leurs logs JSON (`docs/development/logging.md`) :
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
| `--customers` | part des sessions avec un compte (inscription, connexion, commande), de 0 à 1 ; `0` = invités seuls | 0.25 |
| `--typo-rate` | part des connexions précédées d'une faute de mot de passe (échec normal) | 0.1 |
| `--order-rate` | part des clients connectés qui passent commande (0.12 donne ~3 % de conversion globale) | 0.12 |
| `--decline-rate` | part des paiements refusés (méthode de test `pm_test_declined`) | 0.1 |
| `--abandon-rate` | part des commandes jamais payées (elles expirent), et moitié moins qui quittent la page de paiement | 0.25 |
| `--slip-rate` | part des gestes maladroits : saisie ou devis invalide, adresse erronée, double clic | 0.03 |
| `--bursts-per-hour` | rafales de visiteurs légitimes par heure (×2 à ×3,5 pendant 1 à 2,5 min) | 3 |
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

## Comptes, commandes et paiement

Trois parcours se partagent les sessions (`--customers` règle la part des deux derniers) :

| Parcours | Part | Ce qu'il fait |
|---|---|---|
| invité | 70 % | navigation décrite ci-dessus |
| nouveau client | 9 % | `POST /api/auth/register`, `POST /login` (l'email n'a pas besoin d'être vérifié), `GET /me`, navigation, commande éventuelle ; son compte rejoint le groupe des comptes réutilisables |
| client connu | 21 % | reprend un compte du groupe : `POST /login` (parfois après une faute de mot de passe), `GET /me`, navigation, commande éventuelle, `GET /api/shop/me/orders` |

Une commande enchaîne `POST /api/shop/orders` (clé `Idempotency-Key`, 1 à 2 produits en quantité 1, adresse fictive),
`POST /orders/{id}/pay` puis `POST /orders/{id}/pay/confirm`. `payment` n'est pas exposé par la passerelle : son trafic
vient du shop. Un paiement sur dix est refusé (`pm_test_declined`) et, une fois sur deux, suivi d'un nouvel essai réussi.

**Limites respectées** (le générateur y reste volontairement sous la barre, sans jamais provoquer de 429) :

- **Passerelle, `register` et `login`** : 60 requêtes par minute et par IP, rafale de 30 -> limiteur interne de 40 par minute, rafale 20.
- **Passerelle, tout `/api/shop/orders*`** (création, demande et confirmation de paiement comptent chacune) : 10 par minute,
  rafale 5 -> limiteur interne de 8 par minute, rafale 4. Sans jeton disponible, le visiteur renonce à commander (ou se comporte en invité).
- **Verrouillage d'auth** (5 échecs de connexion en 15 minutes verrouillent le compte) : une seule faute de frappe par visite,
  toujours suivie du bon mot de passe, qui remet le compteur à zéro. Un compte n'est prêté qu'à un visiteur à la fois.
- Pas de cookie conservé entre visiteurs (le jeton de rafraîchissement n'est jamais réutilisé).

Ces garanties sont vérifiées par `test_full_stack_simulation` (fausse pile qui applique les mêmes limites et le
verrouillage : 0 réponse 429, au plus 1 échec consécutif par compte, même à 120 visiteurs par minute).

À savoir : chaque inscription crée un vrai compte dans la base d'`auth` (identifiants jetables, adresses `@example.com`),
et chaque commande réserve du stock : quelques produits ont un petit stock et peuvent donner des refus `409` au bout de
nombreuses commandes. Les emails de vérification arrivent dans Mailpit, que le générateur ne lit pas.

## Réalisme : refus, abandons, popularité, rafales

**Refus et erreurs produits** (tous « normaux » : des humains qui se trompent, pas des attaques) :

| Service | Geste | Réponse | Événement journalisé |
|---|---|---|---|
| auth | mot de passe faux (`--typo-rate`) | 401 | `auth.login_failed` (denied) |
| auth | adresse de connexion inconnue, toujours différente (`--slip-rate`) | 401 | `auth.login_failed`, `unknown_account` |
| auth | inscription avec un mot de passe trop court ou une adresse invalide | 422 | `auth.registration_rejected` |
| auth | double clic sur « créer mon compte » | 202 | (réponse neutre, sans révéler que le compte existe) |
| shop | produit introuvable (`--refusal-rate`) | 404 | `catalog.product_not_found` |
| shop | listing avec une catégorie inconnue | 422 | `catalog.query_rejected` |
| shop | devis avec un produit en double ou inconnu | 422 | `cart.quote_rejected` |
| shop | double clic sur « commander » (même clé d'idempotence) | 200 | même commande, aucun doublon |
| shop | suivi de commande avec une adresse erronée | 404 | `order.lookup_denied` (`order_not_found`) |
| payment (via le shop) | paiement refusé, parfois réessayé | 200 `failed` | `order.payment_failed` |
| payment (via le shop) | double confirmation d'une commande payée | 409 | `order.payment_rejected` (`order_already_paid`) |
| shop | stock insuffisant (naturel, petit stock) | 409 | `stock.insufficient` |

**Entonnoir** : environ 25 % des sessions ont un compte et 12 % d'entre elles commandent (~3 % de conversion). Un quart des
commandes n'est jamais payé (le shop les fait expirer), un paiement sur dix est refusé.

**Popularité** : les produits sont vus selon une loi de Zipf (rang fixe par identifiant) : quelques produits concentrent
l'essentiel des visites, les autres sont rares. **Rafales** : quelques pics légitimes, multipliés par 2 à 3,5, pour que le
détecteur apprenne qu'un pic court n'est pas forcément une attaque. **Durées** : 8 % des pauses sont longues (20 s en moyenne),
d'où des sessions de durée très inégale.

Sont volontairement absents du trafic normal : verrouillage de compte, rafales de 401 ou de 404, erreurs 5xx, 429.
Ils sont des signaux d'attaque ou de panne : ils viendront avec les scénarios d'incident.

À savoir : tant que les comptes ne vérifient pas leur email, chaque action d'un client produit un refus
`order.guest_link_skipped` (`email_not_verified`) qui n'existerait pas pour des clients ayant vérifié leur adresse.

## Architecture (calquée sur les services Basecamp)

Un projet `uv` autonome, tranche verticale `traffic`, un fichier = une classe, tests dans `__tests__/`.

```
app/
  core/settings.py                      configuration TG_*
  traffic/
    domain/          entities, enums (PaymentMethod...), value_objects (CartLine, SessionProfile, Account, OrderRequest),
                     interfaces (ShopGateway, AuthGateway, OrderGateway, AccountPool, Journey, Timer, Spawner),
                     services (ThinkTimePolicy, SessionProfilePicker, LoadProfile, TokenBucket, AccountFactory...)
    application/     BrowseShop (invité), NewCustomerJourney, ReturningCustomerJourney, CustomerSession, OrderFlow,
                     JourneyMix, RunTraffic (arrivées, durée, rythme)
    infrastructure/  HttpxShopGateway, HttpxAuthGateway, HttpxOrderGateway (HTTP via la passerelle), HttpxRequester,
                     InMemoryAccountPool, SystemTimer, ThreadSpawner
    presentation/    cli.py (point d'entrée et assemblage)
```

Règle de dépendance vérifiée par `app/__tests__/unit/test_architecture.unit.py` : `domain` n'importe rien d'extérieur,
`application` seulement `domain`, `infrastructure` ni `application` ni `presentation`.

## Développement

Python 3.12 (épinglé dans `.python-version`), gestion des dépendances avec uv.

```powershell
uv run poe quality    # lint (ruff), formatage (ruff format --check) et types (mypy) : ce que la CI rend bloquant
uv run poe security   # audit des dépendances (pip-audit) : échoue dès une vulnérabilité connue
uv run poe test       # tests et couverture (seuil 80 %)
uv run poe check      # qualité, audit puis tests
uv run poe format     # corrige le formatage
```

### Hooks Git

Trois hooks vérifient, sans jamais corriger les fichiers ni se contourner (`--no-verify` interdit). Installation, une fois :

```powershell
uv run pre-commit install --install-hooks
```

| Hook | Contrôles |
|---|---|
| `commit-msg` | message au format Conventional Commit : `<type>(<portée>)?: <description>` (types : feat, fix, docs, chore, refactor, test, ci, build, perf, style, revert) |
| `pre-commit` | gitleaks sur l'index, puis lint et formatage |
| `pre-push` | gitleaks sur les commits poussés (même plage que la CI), puis types et tests |

Le hook `pre-push` demande le binaire `gitleaks` sur le PATH, en version 8.30.1 (la même que la CI) :
voir [gitleaks](https://github.com/gitleaks/gitleaks#installing) (par exemple `winget install gitleaks`, ou `scoop install gitleaks`).

### Intégration continue

`.github/workflows/ci.yml` tourne sur chaque PR vers `main` et à chaque push sur `main`. Il rejoue les tâches des hooks :

| Job | Contenu |
|---|---|
| `python` | installation figée (`uv sync`, Python 3.12, roues uniquement), `poe quality`, `poe test` (couverture ≥ 80 %), `poe security` |
| `secrets-scan` | gitleaks (v8.30.1, archive vérifiée par son SHA-256) sur les seuls commits apportés par la PR ou le push |
| `pr-title` | le titre de la PR respecte Conventional Commits (même script que le hook `commit-msg`) |
| `ci-ok` | job final, **seul check à rendre obligatoire** dans la protection de la branche `main` |

Pour rejouer la CI en local : `uv run poe check`. Les actions GitHub sont épinglées par SHA complet.

Documentation détaillée : [runbook CI](docs/ci.md), [publier un changement](docs/publier.md), [retour arrière](docs/retour-arriere.md).

## Limites

- Trafic normal uniquement : pas de flood (à ajouter comme nouveau cas d'usage dans `application/`).
- Les comptes ne vivent que le temps d'une exécution (pas de fichier d'identifiants) : une nouvelle exécution recrée des comptes.
- Pas de vérification d'email, de réinitialisation de mot de passe, de jeton expiré, de déconnexion ni de routes d'administration.
- Les refus produits : produit introuvable (404), échec de connexion (401), paiement refusé, parfois stock insuffisant (409).
  Les devis invalides ou les erreurs 5xx ne sont pas simulés.
- À lancer uniquement contre la pile locale du projet.
