# Suivi des candidatures

Radar d'offres d'emploi et suivi des candidatures, **multi-profils**.

- Un **collecteur** (Python) tourne chaque matin sur GitHub Actions : il interroge les sources, dédoublonne, calcule un score de pertinence pour chaque profil et enregistre le résultat dans `data/`.
- Une **appli web statique** (HTML/CSS/JS, sans build) publiée sur GitHub Pages affiche les offres triées, les échéances, les liens rapides et l'état des sources. Le suivi (statuts, notes) reste dans le navigateur de chaque utilisateur.

```
.github/workflows/collect.yml   collecte quotidienne + commit des données
collector/                      le collecteur
  main.py                       orchestration : sources → dédoublonnage → score par profil
  scoring.py                    score piloté par profile.yml
  sources/                      une source = un module (France Travail, Adzuna, CNRS…)
config/sources.yml              sources actives et leurs réglages (commun à tous)
profiles/<id>/profile.yml       un profil = requêtes, catégories, compétences, échéances, liens
profiles/<id>/manual.json       offres ajoutées à la main pour ce profil
profiles/_modele/               modèle à copier pour un nouvel utilisateur
data/                           généré par le collecteur (ne pas modifier à la main)
index.html, app.js, styles.css  l'appli web
tests/                          tests hors-ligne
```

## 1. Mise en route

### Pousser le dépôt

```bash
cd ~/app_candidature
git init
git add .
git commit -m "Radar d'offres : collecteur et appli"
git branch -M main
git remote add origin https://github.com/<identifiant>/app_candidature.git
git push -u origin main
```

### Ajouter les clés d'API (secrets)

Dans le dépôt GitHub : **Settings → Secrets and variables → Actions → New repository secret**. Crée ces quatre secrets :

| Nom | Où le trouver |
|---|---|
| `FRANCE_TRAVAIL_CLIENT_ID` | francetravail.io → ton application → identifiant client |
| `FRANCE_TRAVAIL_CLIENT_SECRET` | francetravail.io → ton application → clé secrète |
| `ADZUNA_APP_ID` | developer.adzuna.com → Dashboard → Application ID |
| `ADZUNA_APP_KEY` | developer.adzuna.com → Dashboard → Application Key |

Sur francetravail.io, l'application doit être **abonnée à l'API « Offres d'emploi v2 »**, sinon l'authentification est refusée.

Les clés ne doivent jamais être écrites dans un fichier du dépôt.

### Autoriser le collecteur à enregistrer les données

**Settings → Actions → General → Workflow permissions → Read and write permissions → Save.**

### Publier l'appli

**Settings → Pages → Deploy from a branch → `main` / `(root)` → Save.**
L'appli est en ligne après une minute à `https://<identifiant>.github.io/app_candidature/`.

### Lancer la première collecte

**Actions → Collecte des offres → Run workflow.** Quand c'est fini, l'onglet **Sources** de l'appli montre ce que chaque source a renvoyé. Ensuite, la collecte tourne seule chaque matin.

## 2. Ajuster la recherche

Tout se règle dans `profiles/<id>/profile.yml` : chaque modification déclenche une nouvelle collecte.

- `search.queries` : les métiers recherchés (tous secteurs confondus).
- `categories` : comment classer une offre d'après son intitulé (la première qui correspond l'emporte).
- `skills` : compétences et leur poids dans le score (×1,5 si elles sont dans l'intitulé).
- `exclude_title`, `penalties` : intitulés exclus et malus.
- `locations` : bonus géographique.
- `min_score`, `fit` : seuil d'affichage et seuils des badges.
- `echeances`, `liens` : onglets Échéances et Liens rapides.

Les sources elles-mêmes se règlent dans `config/sources.yml` (désactiver une source, régions CNRS et Hellowork, budget Adzuna, flux RSS supplémentaires).

## 3. Ajouter un utilisateur

1. Copier `profiles/_modele/` en `profiles/<prenom>/` (sans tiret bas au début).
2. Adapter `profile.yml`.
3. Commit et push : le collecteur crée `data/profiles/<prenom>/`.
4. L'appli propose alors un sélecteur de profil. On peut aussi donner un lien direct : `…/app_candidature/?p=<prenom>`.

Chaque source n'est interrogée qu'une fois pour tous les profils ; le score est calculé séparément pour chacun.

## 4. Ajouter une source

1. Créer `collector/sources/ma_source.py` avec une classe dérivée de `Source` qui implémente `fetch(ctx)` et renvoie une liste d'`Offer`.
2. L'enregistrer dans `collector/sources/__init__.py` (dictionnaire `ALL`).
3. L'activer dans `config/sources.yml`.

Pour un simple flux RSS, inutile d'écrire du code : l'ajouter sous `rss.feeds` dans `config/sources.yml`.

Une source qui échoue n'empêche jamais les autres de tourner : son erreur apparaît dans l'onglet Sources.
Pour diagnostiquer un extracteur HTML, lancer le workflow à la main en cochant **debug** : une copie des pages lues est enregistrée dans `data/_debug/`.
Les sources HTML respectent `robots.txt` et espacent leurs requêtes.

## 5. Tester en local

```bash
pip install -r requirements.txt
python -m unittest discover -s tests        # tests hors-ligne
python -m collector --offline               # recalcule les fichiers sans contacter les sources
python3 -m http.server                      # puis ouvrir http://localhost:8000
```

Pour une vraie collecte en local, exporter d'abord les quatre variables d'environnement des clés.

## Confidentialité

Avec un compte GitHub gratuit, Pages ne publie que les dépôts **publics** : la liste des offres et les profils (`profile.yml`) sont visibles par tous. Les statuts et les notes, eux, ne quittent jamais le navigateur. Ne commite pas d'export de suivi.

## Attribution

Les offres France Travail et Adzuna sont affichées avec leur source et un lien vers l'annonce d'origine, comme le demandent leurs conditions d'utilisation.
