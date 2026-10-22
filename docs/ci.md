# Intégration continue : runbook

Ce document décrit ce que contrôle la CI de Traffic-Generator, comment la rejouer en local et que faire quand elle échoue.

## Principe

- Un seul workflow : `.github/workflows/ci.yml`. Il se déclenche sur chaque PR vers `main` (ouverture, nouveau commit, réouverture, titre modifié) et sur chaque push sur `main`.
- La CI rejoue les tâches `poe` du projet, jamais un outil en direct : ce qui passe en local passe en CI.
- Python 3.12 et dépendances figées sur `uv.lock` (`UV_FROZEN`, roues uniquement).
- Toutes les actions GitHub sont épinglées par SHA complet (la version est en commentaire). Les permissions sont vides par défaut, `contents: read` par job.

## Les jobs

| Job | Ce qu'il fait | Rejouer en local |
|---|---|---|
| `python` | `poe quality` (ruff lint, ruff format --check, mypy), `poe test` (pytest, couverture ≥ 80 %), `poe security` (pip-audit) | `uv run poe check` |
| `secrets-scan` | gitleaks 8.30.1 (archive vérifiée par SHA-256) sur les seuls commits apportés par la PR ou le push | `gitleaks git --redact -v --log-opts="origin/main..HEAD" .` |
| `pr-title` | le titre de la PR respecte Conventional Commits (même script que le hook `commit-msg`) | `python scripts/hooks/check_commit_msg.py <fichier contenant le titre>` |
| `ci-ok` | agrège les jobs ci-dessus : vert si tous sont `success` ou `skipped` | — |

`ci-ok` est le **seul check à rendre obligatoire** dans la protection de la branche `main`. Ajouter un job bloquant, c'est l'ajouter à `needs` de `ci-ok`.

## Quand un job échoue

- **`python` / lint ou format** : `uv run poe format` corrige le formatage ; `uv run poe lint` indique le reste. Pas de `# noqa` sans motif écrit à côté.
- **`python` / types** : `uv run poe typecheck`.
- **`python` / tests ou couverture** : `uv run poe test`. Le seuil de 80 % ne se baisse pas ; on ajoute des tests.
- **`python` / security** : `pip-audit` signale une dépendance vulnérable. Mettre à jour (`uv lock --upgrade-package <nom>`, puis `uv sync`) et relancer `uv run poe check`. Aucune exception silencieuse.
- **`secrets-scan`** : un secret (ou ce qui y ressemble) est dans un commit de la PR. Le retirer **de l'historique de la branche** (réécrire les commits de la branche, avant fusion), puis **révoquer** le secret s'il était réel : un secret poussé est considéré comme compromis. Un faux positif se traite dans `.gitleaks.toml` (règle et chemin précis), jamais par une exception large.
- **`pr-title`** : corriger le titre de la PR (le contrôle se relance tout seul). Format : `<type>(<portée>)?: <description>`, types `feat, fix, docs, chore, refactor, test, ci, build, perf, style, revert`.

Il est interdit de contourner un contrôle : pas de `--no-verify`, pas de test désactivé ou ignoré, pas de règle retirée pour faire passer la CI.

## Hooks Git

Les hooks rejouent une partie de la CI avant le commit et le push (voir le README, section « Hooks Git »). Installation, une fois :

```powershell
uv run pre-commit install --install-hooks
```

`gitleaks` 8.30.1 doit être installé (`winget install gitleaks`), la même version que la CI.
