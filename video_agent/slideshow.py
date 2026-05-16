"""
Rendu vidéo à partir d'un brief JSON : diapositives + montage MP4 (FFmpeg).
Option : synthèse vocale (Microsoft Edge TTS, gratuit, sans clé API) via le module edge_tts.
À exécuter en local — Vercel ne convient pas à l'encodage long.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from video_agent.planner import DEFAULT_CLIP_TARGET_SECONDS, build_brief

MIN_SLIDE_SECONDS = 0.5
DEFAULT_WIDTH, DEFAULT_HEIGHT = 1280, 720
TTS_CHAR_LIMIT = 4500
DEFAULT_FRENCH_VOICE = "fr-FR-DeniseNeural"


def _pick_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        p = Path(path)
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap(text: str, width: int) -> str:
    lines: list[str] = []
    for block in text.splitlines():
        if not block.strip():
            lines.append("")
            continue
        lines.extend(textwrap.wrap(block, width=width) or [""])
    return "\n".join(lines)


def render_slide_image(
    title: str,
    body: str,
    *,
    size: tuple[int, int] = (DEFAULT_WIDTH, DEFAULT_HEIGHT),
) -> Image.Image:
    w, h = size
    img = Image.new("RGB", (w, h), color=(12, 13, 16))
    draw = ImageDraw.Draw(img)
    margin = 56
    title_font = _pick_font(44)
    body_font = _pick_font(26)
    title_wrapped = _wrap(title, 34)
    body_wrapped = _wrap(body, 52)
    y = margin
    draw.multiline_text((margin, y), title_wrapped, font=title_font, fill=(232, 234, 239), spacing=8)
    y += int(draw.multiline_textbbox((0, 0), title_wrapped, font=title_font)[3] - draw.multiline_textbbox((0, 0), title_wrapped, font=title_font)[1]) + 28
    draw.multiline_text((margin, y), body_wrapped, font=body_font, fill=(154, 163, 178), spacing=6)
    return img


def slides_from_brief(data: dict[str, Any]) -> list[tuple[str, str, float]]:
    """Retourne (titre, corps, durée_secondes) pour chaque plan."""
    modular = data.get("modular_assembly") or {}
    clips = modular.get("clips") if isinstance(modular, dict) else None
    out: list[tuple[str, str, float]] = []
    if isinstance(clips, list) and clips:
        for c in clips:
            if not isinstance(c, dict):
                continue
            title = str(c.get("title", "Sans titre"))
            cid = str(c.get("id", ""))
            head = f"{cid} — {title}" if cid else title
            tps = c.get("talking_points") or []
            body_lines = [str(x) for x in tps if str(x).strip()]
            body = "\n".join(body_lines) if body_lines else str(c.get("stitch_out", ""))
            dur = float(c.get("target_seconds", 5.0))
            out.append((head, body, max(MIN_SLIDE_SECONDS, dur)))
        return out

    for ch in data.get("chapters") or []:
        if not isinstance(ch, dict):
            continue
        title = str(ch.get("title", "Sans titre"))
        obj = str(ch.get("objective", "")).strip()
        tps = ch.get("talking_points") or []
        bullets = "\n".join(f"• {str(x)}" for x in tps if str(x).strip())
        body = "\n\n".join(p for p in (obj, bullets) if p)
        dur = float(ch.get("target_seconds", 60.0))
        out.append((title, body, max(MIN_SLIDE_SECONDS, dur)))
    return out


def _ffmpeg_bin() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise FileNotFoundError(
            "ffmpeg est introuvable dans le PATH. Installez FFmpeg puis réessayez "
            "(https://ffmpeg.org/download.html)."
        )
    return exe


def _tts_script(title: str, body: str) -> str:
    text = f"{title.strip()}.\n{body.strip()}".strip()
    if len(text) > TTS_CHAR_LIMIT:
        text = text[: TTS_CHAR_LIMIT - 1] + "…"
    return text


def _run_edge_tts(text: str, out_mp3: Path, voice: str) -> None:
    """Synthèse via le service Edge (module edge_tts, sans clé API)."""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as tf:
        tf.write(text)
        tf_path = Path(tf.name)
    try:
        cmd = [
            sys.executable,
            "-m",
            "edge_tts",
            "-f",
            str(tf_path),
            "-v",
            voice,
            "--write-media",
            str(out_mp3),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or "").strip() or str(e)
        raise RuntimeError(
            "edge_tts a échoué. Installez les dépendances : pip install -r requirements.txt\n" + msg
        ) from e
    finally:
        try:
            tf_path.unlink(missing_ok=True)
        except OSError:
            pass


def render_mp4_from_slides(
    slides: list[tuple[str, str, float]],
    output_mp4: Path,
    *,
    fps: int = 25,
    voice: str | None = None,
) -> None:
    if not slides:
        raise ValueError("Aucune diapositive à rendre (brief vide ou JSON invalide).")

    ffmpeg = _ffmpeg_bin()
    output_mp4 = output_mp4.expanduser().resolve()

    if voice:
        _render_with_tts(slides, output_mp4, ffmpeg=ffmpeg, fps=fps, voice=voice)
    else:
        _render_silent(slides, output_mp4, ffmpeg=ffmpeg, fps=fps)


def _render_silent(
    slides: list[tuple[str, str, float]],
    output_mp4: Path,
    *,
    ffmpeg: str,
    fps: int,
) -> None:
    with tempfile.TemporaryDirectory(prefix="briefvid_") as td:
        tmp = Path(td)
        paths: list[Path] = []
        for i, (title, body, dur) in enumerate(slides):
            img = render_slide_image(title, body)
            p = tmp / f"slide_{i:04d}.png"
            img.save(p, format="PNG")
            paths.append(p)

        args: list[str] = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
        for p, (_, _, dur) in zip(paths, slides):
            args += ["-loop", "1", "-t", f"{float(dur):.3f}", "-i", str(p)]

        n = len(slides)
        parts: list[str] = []
        for i in range(n):
            parts.append(
                f"[{i}:v]scale={DEFAULT_WIDTH}:{DEFAULT_HEIGHT}:force_original_aspect_ratio=decrease,"
                f"pad={DEFAULT_WIDTH}:{DEFAULT_HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}[v{i}]"
            )
        concat_in = "".join(f"[v{i}]" for i in range(n))
        parts.append(f"{concat_in}concat=n={n}:v=1:a=0[vout]")
        filter_complex = ";".join(parts)

        args += [
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            str(output_mp4),
        ]
        subprocess.run(args, check=True)


def _render_with_tts(
    slides: list[tuple[str, str, float]],
    output_mp4: Path,
    *,
    ffmpeg: str,
    fps: int,
    voice: str,
) -> None:
    """Un segment MP4 par slide (image en boucle + voix), puis concat en copy."""
    with tempfile.TemporaryDirectory(prefix="briefvidtts_") as td:
        tmp = Path(td)
        segments: list[Path] = []
        for i, (title, body, _planned_dur) in enumerate(slides):
            png = tmp / f"slide_{i:04d}.png"
            mp3 = tmp / f"slide_{i:04d}.mp3"
            seg = tmp / f"seg_{i:04d}.mp4"
            render_slide_image(title, body).save(png, format="PNG")
            _run_edge_tts(_tts_script(title, body), mp3, voice=voice)
            cmd = [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-loop",
                "1",
                "-i",
                str(png),
                "-i",
                str(mp3),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "28",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps),
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "44100",
                "-ac",
                "2",
                "-shortest",
                str(seg),
            ]
            subprocess.run(cmd, check=True)
            segments.append(seg)

        list_path = tmp / "concat.txt"
        lines = "\n".join(f"file '{p.as_posix()}'" for p in segments)
        list_path.write_text(lines + "\n", encoding="utf-8")

        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c",
                "copy",
                str(output_mp4),
            ],
            check=True,
        )


def _load_brief_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Le JSON doit être un objet à la racine.")
    return data


def main() -> None:
    p = argparse.ArgumentParser(
        description="Génère un MP4 à partir d'un brief JSON ou d'un domaine/angle (diaporama ; option voix Edge TTS).",
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--json", type=Path, help="Chemin vers un brief.json (sortie du planificateur).")
    src.add_argument("--domain", help="Avec --angle : régénère le brief sans fichier JSON.")
    p.add_argument("--angle", help="Voir --domain.")
    p.add_argument("--audience", default="curieux du sujet, niveau intermédiaire")
    p.add_argument("--seconds", type=float, default=600.0)
    p.add_argument("--clip-target-seconds", type=float, default=DEFAULT_CLIP_TARGET_SECONDS)
    p.add_argument("--no-modular", action="store_true", help="Ne pas utiliser modular_assembly pour les slides.")
    p.add_argument("-o", "--output", type=Path, default=Path("brief-draft.mp4"), help="Fichier MP4 de sortie.")
    p.add_argument("--fps", type=int, default=25)
    p.add_argument(
        "--speech",
        action="store_true",
        help="Active la synthèse vocale (edge_tts / service Microsoft Edge, sans clé API).",
    )
    p.add_argument(
        "--voice",
        default=DEFAULT_FRENCH_VOICE,
        help=f"Voix edge-tts si --speech (défaut : {DEFAULT_FRENCH_VOICE}). Lister : python3 -m edge_tts -l",
    )
    args = p.parse_args()

    if args.domain:
        if not args.angle:
            p.error("--angle est requis avec --domain.")
        brief = build_brief(args.domain, args.angle, audience=args.audience, total_seconds=args.seconds)
        data = brief.to_dict(modular=not args.no_modular, clip_target_seconds=args.clip_target_seconds)
    else:
        assert args.json is not None
        data = _load_brief_json(args.json)

    slides = slides_from_brief(data)
    voice = args.voice if args.speech else None
    render_mp4_from_slides(slides, args.output, fps=args.fps, voice=voice)
    mode = "voix + images" if voice else "muet (images seules)"
    print(f"Vidéo écrite ({mode}) : {args.output.resolve()}")


if __name__ == "__main__":
    main()
