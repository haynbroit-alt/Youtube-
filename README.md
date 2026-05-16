# Youtube-

Planificateur de brief vidéo (~10 min) : `python3 -m video_agent "votre domaine" "votre angle"` (option `-o fichier.json`).

## Déploiement sur Vercel

1. Connectez le dépôt sur [vercel.com](https://vercel.com) (**Add New → Project**).
2. Laissez **Root Directory** sur la racine du dépôt (branche avec `api/` et `public/`).
3. **Build Command** : vide (ou `echo skip`). **Output Directory** : vide — Vercel sert `public/` automatiquement et compile les fonctions `api/*.py`.
4. Après déploiement : page d’accueil = formulaire ; API = `POST /api/plan` (JSON) ou `GET /api/plan?domain=...&angle=...`.

Exemple `POST` :

```json
{
  "domain": "pâtisserie sans gluten",
  "angle": "3 recettes express",
  "audience": "débutants pressés",
  "seconds": 600
}
```

Réponse : JSON du brief (chapitres, beats, idées B-roll, etc.).

## Développement local

```bash
python3 -m video_agent "domaine" "angle" -o brief.json
```

Pour tester l’API comme sur Vercel, utilisez [Vercel CLI](https://vercel.com/docs/cli) : `vercel dev` à la racine du projet.

## Petites vidéos collées (grande vidéo)

Le JSON peut inclure `modular_assembly` : liste de **clips courts** (`M001`, `M002`, …) avec durées, placement sur la timeline virtuelle, points à traiter par bloc, et **conseils de collage** (audio, J-cut, nommage des fichiers).  
Paramètres API / POST : `modular` (bool, défaut `true`), `clip_target_seconds` (entre 20 et 150, défaut `75`).  
CLI : `--clip-target-seconds 75` et `--no-modular` pour désactiver.

