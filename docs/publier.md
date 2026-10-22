# Publier un changement

Aucun push direct sur `main` : tout passe par une PR, vérifiée par `ci-ok`, fusionnée en squash.

## Pas à pas

1. Partir de `main` à jour :
   ```powershell
   git switch main
   git pull
   git switch -c feat/ma-modification
   ```
   Préfixes de branche usuels : `feat/`, `fix/`, `chore/`, `docs/`, `ci/`.
2. Modifier, puis vérifier en local :
   ```powershell
   uv run poe check
   ```
3. Committer. Message court, en français, au format Conventional Commit : `feat(visiteurs): ajoute un profil de rafale`. Les hooks vérifient le message, les secrets, le lint et le formatage.
4. Pousser la branche (le hook `pre-push` lance gitleaks, les types et les tests) :
   ```powershell
   git push -u origin feat/ma-modification
   ```
5. Ouvrir une PR vers `main`.
   - **Le titre respecte Conventional Commits** : en squash, il devient le message du commit sur `main`, et le job `pr-title` le contrôle.
   - La description donne : quoi, pourquoi, comment tester.
6. Attendre `ci-ok` au vert, faire relire, puis fusionner en **squash**.

## Petites PR, PR empilées

Une PR = un changement cohérent et relisable. Pour un travail en plusieurs tranches, on empile : chaque branche part de la précédente et sa PR vise la précédente. Quand la PR du bas est fusionnée, on change la base de la suivante vers `main` (GitHub le propose), on rebase si besoin, puis on continue.

## Dépendances

Ajouter ou mettre à jour une dépendance passe par uv, qui met à jour `uv.lock` ; le commit contient `pyproject.toml` **et** `uv.lock` :

```powershell
uv add <paquet>            # ou: uv lock --upgrade-package <paquet>
uv run poe check
```

## Ce qu'on ne fait pas

- pas de secret dans le dépôt, dans un commit, une PR ou un message (utiliser les variables d'environnement, `.env` est ignoré par Git) ;
- pas de `--no-verify`, pas de test ignoré, pas de règle de lint ou de sécurité désactivée pour « faire passer » ;
- pas de push direct sur `main`, pas de `push --force` sur `main`.
