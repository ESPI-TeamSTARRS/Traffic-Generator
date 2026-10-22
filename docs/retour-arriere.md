# Retour arrière

Traffic-Generator est un outil lancé à la demande (`uv run poe normal`) : il n'est pas déployé en continu, donc revenir en arrière consiste à revenir à un état sain de `main`.

## Choisir la bonne voie

| Situation | Action |
|---|---|
| La PR n'est pas encore fusionnée | corriger la branche (nouveau commit) ou fermer la PR |
| Un changement fusionné est défectueux et le correctif est évident | PR de correctif courte (`fix: ...`) |
| Un changement fusionné est défectueux et il faut revenir vite à l'état précédent | PR de **revert** |

On ne réécrit jamais l'historique de `main` (pas de `reset --hard` suivi d'un push forcé).

## Revert d'une PR fusionnée

Les PR sont fusionnées en squash : une PR = un commit sur `main`, donc un seul commit à annuler.

```powershell
git switch main
git pull
git switch -c fix/revert-ma-modification
git revert <sha-du-commit-squash>
```

Le message proposé par Git (`Revert "..."`) doit être mis au format Conventional Commit, par exemple `revert: annule l'ajout du profil de rafale`. Pousser la branche, ouvrir une PR, attendre `ci-ok`, fusionner en squash.

Si le commit à annuler a été suivi de modifications qui en dépendent, le revert peut entrer en conflit : le résoudre à la main, puis `uv run poe check`.

## Dépendance défectueuse

Revenir à la version précédente dans `pyproject.toml`, relancer `uv lock`, vérifier avec `uv run poe check`, puis publier par une PR (`fix(deps): ...`). Le revert du commit de mise à jour fait la même chose.

## Secret poussé par erreur

Retirer le secret du dépôt ne suffit pas : **le révoquer et en émettre un nouveau** d'abord. Ensuite seulement nettoyer, par une PR (et, si le secret est dans l'historique de `main`, en prévenir l'équipe avant toute réécriture).
