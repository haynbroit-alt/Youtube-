# Youtube-

Planificateur de brief vidéo (~10 min) : `python3 -m video_agent "votre domaine" "votre angle"` (option `-o fichier.json`).

## Déploiement sur Vercel

> **Erreur** `functions` / `api/**/*.py` : sur Vercel, ce glob ne cible pas toujours `api/plan.py`. Ce dépôt utilise `api/plan.py` dans `vercel.json`. Si l’erreur persiste, vérifiez que la branche déployée contient bien `api/plan.py` (fusionnez les PR si besoin).

1. Connectez le dépôt sur [vercel.com](https://vercel.com) (**Add New → Project**).
2. Laissez **Root Directory** sur la racine du dépôt (branche avec `api/` et `public/`).
3. **Framework / build** : le dépôt fixe `framework: null` (« Other ») et `outputDirectory: "public"` dans `vercel.json`, avec `package.json` et le script `npm run build` (no-op) pour éviter les échecs si l’assistant d’import a laissé un **Output Directory** invalide (ex. `dist`, `.next`) ou un **framework** cassé dans l’URL (`framework=|`).
4. Si un déploiement existant échoue encore : **Project → Settings → General → Framework Preset** = **Other** ; **Build Command** = `npm run build` ; **Output Directory** = `public` (ou laissez le dépôt piloter via `vercel.json`).
5. Après déploiement : page d’accueil = formulaire ; API = `POST /api/plan` (JSON) ou `GET /api/plan?domain=...&angle=...`.

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

## Génération d’une vidéo (MP4 brouillon, local)

Vercel **ne remplace pas** un studio : l’encodage FFmpeg long, la voix et les vraies images passent mieux sur votre machine ou sur un service spécialisé (Runway, ElevenLabs, etc.).

Ce dépôt inclut toutefois un **rendu MP4 « diaporama »** : une image par chapitre (ou par clip si `modular_assembly` est présent), durées alignées sur le brief, montage **H.264** via **FFmpeg**.

Prérequis : `ffmpeg` dans le `PATH`, puis :

```bash
pip install -r requirements.txt
python3 -m video_agent.slideshow --domain "Votre sujet" --angle "Votre angle" -o ma-video.mp4
```

À partir d’un JSON déjà téléchargé :

```bash
python3 -m video_agent.slideshow --json brief.json -o ma-video.mp4
```

Options utiles : `--seconds`, `--clip-target-seconds`, `--no-modular`, `--fps`.

C’est une **base visuelle** pour enregistrer la voix par-dessus ou pour itérer avant un montage « réel ».

### Voix automatique (sans clé API)

Avec **`edge-tts`** (Microsoft Edge TTS, via `pip install -r requirements.txt`) :

```bash
python3 -m video_agent.slideshow --domain "Votre sujet" --angle "Votre angle" --speech -o video-parlee.mp4
```

Voix par défaut : `fr-FR-DeniseNeural`. Autres voix : `python3 -m edge_tts -l` puis `--voice …`.

