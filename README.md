# Suivi des candidatures

Application web statique pour suivre des offres d'emploi (enseignement, postdoc, data science, data analyse) : filtres, tri par pertinence ou date limite, statut et notes par offre, ajout d'offres depuis l'interface.

Aucun build, aucune dépendance : HTML, CSS et JavaScript seulement.

## Déployer sur GitHub Pages

1. Crée un dépôt sur GitHub (par exemple `suivi-candidatures`).
2. Envoie les fichiers :
   ```bash
   cd suivi-candidatures
   git init
   git add .
   git commit -m "Première version"
   git branch -M main
   git remote add origin https://github.com/<ton-identifiant>/suivi-candidatures.git
   git push -u origin main
   ```
3. Sur GitHub : **Settings → Pages → Build and deployment → Source : Deploy from a branch**, branche `main`, dossier `/ (root)`, puis **Save**.
4. Après une minute, l'application est en ligne à `https://<ton-identifiant>.github.io/suivi-candidatures/`.

> Sur un compte GitHub gratuit, Pages ne publie que les dépôts **publics** : la liste des offres sera visible par tout le monde. Tes statuts et tes notes, eux, restent dans ton navigateur et ne sont jamais publiés.

## Tester en local

Ouvre simplement `index.html` dans le navigateur (double-clic).

## Ajouter ou modifier des offres

Deux façons :

- **Dans le dépôt** : édite `data/offres.js`, puis commit et push. Chaque offre a ces champs :

  | Champ | Valeurs |
  |---|---|
  | `id` | identifiant unique, sans espace |
  | `type` | `ens` (enseignement / EC), `pd` (postdoc), `ds` (data scientist), `da` (data analyst) |
  | `fit` | `hi` (très bon), `mid` (correct), `lo` (partiel) |
  | `org`, `title`, `location`, `contract` | texte libre |
  | `deadline`, `published` | `"AAAA-MM-JJ"` ou `null` |
  | `why` | pourquoi l'offre te correspond |
  | `contact` | e-mail du contact, ou `""` |
  | `url` | lien vers l'annonce |

- **Dans l'application** : bouton **+ Ajouter une offre**. L'offre est gardée dans ton navigateur. Pour l'intégrer au dépôt, clique **Télécharger offres.js** et remplace `data/offres.js` par ce fichier.

## Sauvegarde du suivi

Statuts, notes et offres ajoutées sont enregistrés dans le `localStorage` du navigateur. Pour les retrouver sur un autre appareil : **Exporter mon suivi** (fichier JSON), puis **Importer un suivi** sur l'autre appareil.

> Ne commite pas ton export de suivi si le dépôt est public : il contient tes notes personnelles.

## Structure

```
index.html       page principale
styles.css       styles (thème clair et sombre)
app.js           logique : filtres, tri, statuts, notes, import/export
data/offres.js   liste des offres
.nojekyll        désactive Jekyll sur GitHub Pages
```
