"""
Planificateur de contenu long format (~10 minutes).
Produit une structure exploitable par des outils externes (LLM, TTS, éditeur).
Inclut un plan « petits clips collés » pour fabriquer une grande vidée par assemblage.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any


DEFAULT_TOTAL_SECONDS = 600  # 10 minutes
DEFAULT_CLIP_TARGET_SECONDS = 75.0
CLIP_TARGET_MIN = 20.0
CLIP_TARGET_MAX = 150.0


@dataclass
class Beat:
    """Un instant clé dans un chapitre."""

    label: str
    seconds_from_chapter_start: float
    note: str


@dataclass
class Chapter:
    title: str
    target_seconds: float
    objective: str
    talking_points: list[str]
    beats: list[Beat] = field(default_factory=list)
    b_roll_ideas: list[str] = field(default_factory=list)


@dataclass
class ModularClip:
    """Un bloc court à tourner ou à exporter seul, puis à enchaîner au montage."""

    id: str
    chapter_index: int
    part_index: int
    parts_in_chapter: int
    title: str
    target_seconds: float
    timeline_start_seconds: float
    timeline_end_seconds: float
    talking_points: list[str]
    stitch_out: str
    stitch_in_next: str


@dataclass
class ProductionBrief:
    domain: str
    angle: str
    audience: str
    total_seconds: float
    chapters: list[Chapter]
    hook_opening: str
    cta_closing: str
    seo_keywords: list[str]

    def to_json(
        self,
        indent: int = 2,
        *,
        modular: bool = False,
        clip_target_seconds: float = DEFAULT_CLIP_TARGET_SECONDS,
    ) -> str:
        return json.dumps(
            self.to_dict(modular=modular, clip_target_seconds=clip_target_seconds),
            ensure_ascii=False,
            indent=indent,
        )

    def to_dict(
        self,
        *,
        modular: bool = False,
        clip_target_seconds: float = DEFAULT_CLIP_TARGET_SECONDS,
    ) -> dict[str, Any]:
        def chapter_dict(c: Chapter) -> dict[str, Any]:
            d = asdict(c)
            d["beats"] = [asdict(b) for b in c.beats]
            return d

        out: dict[str, Any] = {
            "domain": self.domain,
            "angle": self.angle,
            "audience": self.audience,
            "total_seconds": self.total_seconds,
            "chapters": [chapter_dict(c) for c in self.chapters],
            "hook_opening": self.hook_opening,
            "cta_closing": self.cta_closing,
            "seo_keywords": self.seo_keywords,
        }
        if modular:
            out["modular_assembly"] = build_modular_assembly_dict(
                self.chapters,
                clip_target_seconds=clip_target_seconds,
            )
        return out


def _split_list_round_robin(items: list[str], n: int) -> list[list[str]]:
    if n <= 0:
        return [list(items)]
    buckets: list[list[str]] = [[] for _ in range(n)]
    for i, it in enumerate(items):
        buckets[i % n].append(it)
    return buckets


def _clamp_clip_target(seconds: float) -> float:
    return max(CLIP_TARGET_MIN, min(CLIP_TARGET_MAX, float(seconds)))


def build_modular_clips(chapters: list[Chapter], clip_target_seconds: float = DEFAULT_CLIP_TARGET_SECONDS) -> list[ModularClip]:
    """
    Découpe chaque chapitre en blocs courts (cible ~clip_target_seconds)
    pour tourner / exporter séparément puis coller sur la timeline.
    """
    target = _clamp_clip_target(clip_target_seconds)
    clips: list[ModularClip] = []
    global_idx = 0
    timeline = 0.0

    for ci, chapter in enumerate(chapters, start=1):
        dur = max(1.0, float(chapter.target_seconds))
        n_parts = max(1, math.ceil(dur / target))
        part_dur = dur / n_parts
        tp_buckets = _split_list_round_robin(chapter.talking_points, n_parts)

        for k in range(n_parts):
            global_idx += 1
            cid = f"M{global_idx:03d}"
            t0, t1 = timeline, timeline + part_dur
            title = chapter.title if n_parts == 1 else f"{chapter.title} — bloc {k + 1}/{n_parts}"

            stitch_out = (
                "Finir sur une phrase complète ; laisser 0,5–1 s de silence ou room tone "
                "(facilite le recouvrement audio)."
            )
            stitch_next = ""
            if k < n_parts - 1:
                stitch_next = (
                    "Bloc suivant : enchaîner à voix sur le même ton ; privilégier une coupe "
                    "« au souffle » plutôt qu'au milieu d'un mot."
                )
            elif ci < len(chapters):
                stitch_next = (
                    "Chapitre suivant : option J-cut (son du bloc suivant commence sous le B-roll "
                    "de fin) pour masquer la couture."
                )

            clips.append(
                ModularClip(
                    id=cid,
                    chapter_index=ci,
                    part_index=k + 1,
                    parts_in_chapter=n_parts,
                    title=title,
                    target_seconds=round(part_dur, 2),
                    timeline_start_seconds=round(t0, 2),
                    timeline_end_seconds=round(t1, 2),
                    talking_points=tp_buckets[k] if k < len(tp_buckets) else [],
                    stitch_out=stitch_out,
                    stitch_in_next=stitch_next,
                )
            )
            timeline = t1

    return clips


def build_modular_assembly_dict(
    chapters: list[Chapter],
    *,
    clip_target_seconds: float = DEFAULT_CLIP_TARGET_SECONDS,
) -> dict[str, Any]:
    clips = build_modular_clips(chapters, clip_target_seconds)
    target = _clamp_clip_target(clip_target_seconds)
    return {
        "philosophy": (
            "Stratégie « petite vidéo × N » : vous enregistrez ou exportez des blocs courts "
            "numérotés, puis vous les assemblez sur une timeline unique — même logique que les "
            "gros YouTubeurs qui tournent par séquences."
        ),
        "clip_target_seconds": target,
        "clips": [asdict(c) for c in clips],
        "filename_convention": "M###_slug-court-descriptif.mp4 (### = ordre du montage)",
        "techniques_collage": [
            "Même réglage caméra (balance des blancs, ISO) pour tous les blocs d'un même chapitre.",
            "Audio : même distance micro, même pièce ; enlever bruit de fond entre blocs ou garder une room tone cohérente.",
            "Transitions : coupe sèche + 2–4 images B-roll entre deux blocs plutôt que fondus « génériques ».",
            "Phrase de liaison écrite à l'avance entre bloc k et k+1 pour éviter le « euh » au collage.",
            "Export intermédiaire en même résolution / cadence que le projet final pour éviter les re-timecodes.",
        ],
        "checks_avant_publication": [
            "Vérifier que la somme des durées des clips ≈ durée cible du brief.",
            "Normaliser les pics audio entre clips (-14 à -16 LUFS type podcast/voix).",
            "Regarder les 3 s avant/après chaque coupe : œil sur le cadrage et le clignement.",
        ],
    }


def _chapter_templates(domain: str, angle: str) -> list[dict[str, Any]]:
    """Gabarits réutilisables ; le domaine injecte le vocabulaire."""
    return [
        {
            "title": "Pourquoi ce sujet compte maintenant",
            "objective": "Créer l'enjeu émotionnel et intellectuel.",
            "talking_points": [
                f"Contexte actuel dans le domaine « {domain} »",
                "Ce que l'on croit souvent à tort",
                f"L'angle « {angle} » et ce qu'il change",
            ],
            "beats": [
                Beat("accroche", 0.0, "Phrase choc ou statistique en 10–15 s"),
                Beat("promesse", 45.0, "Ce que le spectateur saura à la fin"),
            ],
            "b_roll_ideas": ["plans larges", "interface / objet métier", "courbe ou schéma simple"],
        },
        {
            "title": "Les fondamentaux en clair",
            "objective": "Poser les définitions sans jargon inutile.",
            "talking_points": [
                "3 définitions max, une phrase chacune",
                "Analogie du quotidien",
                "Erreur classique à éviter",
            ],
            "beats": [
                Beat("définition clé", 30.0, "Une idée = un exemple"),
            ],
            "b_roll_ideas": ["texte à l'écran minimal", "animation légère"],
        },
        {
            "title": "Mise en pratique",
            "objective": "Montrer comment appliquer tout de suite.",
            "talking_points": [
                "Étapes numérotées (3 à 5)",
                "Critère de succès mesurable",
                "Piège et comment le contourner",
            ],
            "beats": [
                Beat("démo ou cas", 60.0, "Walkthrough ou mini-scénario"),
            ],
            "b_roll_ideas": ["capture d'écran", "plan serré sur les mains / outil"],
        },
        {
            "title": "Aller plus loin",
            "objective": "Donner de la profondeur sans perdre le fil.",
            "talking_points": [
                "Limites de l'approche naïve",
                "Quand faire appel à un expert / outil",
                "Ressource ou référence (livre, norme, chaîne)",
            ],
            "beats": [
                Beat("nuance", 45.0, "« Oui, mais si… »"),
            ],
            "b_roll_ideas": ["citation courte à l'écran", "logo institutionnel flouté si besoin"],
        },
        {
            "title": "Synthèse et prochain pas",
            "objective": "Verrouiller la mémoire et l'action.",
            "talking_points": [
                "Rappel des 3 idées fortes",
                "Une action concrète sous 24 h",
                "Question ouverte au commentaire",
            ],
            "beats": [
                Beat("récap", 0.0, "Liste visuelle 3 puces"),
                Beat("CTA", 90.0, "Abonnement / playlist / lien"),
            ],
            "b_roll_ideas": ["écran fin avec liens"],
        },
    ]


def build_brief(
    domain: str,
    angle: str,
    *,
    audience: str = "curieux du sujet, niveau intermédiaire",
    total_seconds: float = DEFAULT_TOTAL_SECONDS,
) -> ProductionBrief:
    """
    Construit un brief à partir d'un domaine et d'un angle éditorial.

    Ce n'est pas la vidéo elle-même : c'est le plan que votre pipeline
    (LLM, voix, montage) peut remplir et affiner. Utilisez to_dict(modular=True)
    pour le découpage en petits clips à assembler.
    """
    templates = _chapter_templates(domain, angle)
    n = len(templates)
    per = total_seconds / n
    chapters: list[Chapter] = []
    for t in templates:
        chapters.append(
            Chapter(
                title=t["title"],
                target_seconds=per,
                objective=t["objective"],
                talking_points=list(t["talking_points"]),
                beats=list(t["beats"]),
                b_roll_ideas=list(t["b_roll_ideas"]),
            )
        )

    minutes = max(1, int(round(total_seconds / 60)))
    hook = (
        f"En {minutes} minutes : ce que « {domain} » change pour vous, "
        f"avec l'angle « {angle} » — sans blabla."
    )
    cta = "Notez votre prochaine action dans les commentaires ; on s'en sert pour une suite."

    seo = [
        domain.lower(),
        angle.lower().replace(" ", "-")[:48],
        "explication",
        "tutoriel",
    ]

    return ProductionBrief(
        domain=domain,
        angle=angle,
        audience=audience,
        total_seconds=total_seconds,
        chapters=chapters,
        hook_opening=hook,
        cta_closing=cta,
        seo_keywords=seo,
    )


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Brief vidéo ~10 min (structure JSON).")
    p.add_argument("domain", help="Ex. astrophysique, pâtisserie, RGPD")
    p.add_argument("angle", help="Ex. 'pour débutants', 'mythes vs réalité'")
    p.add_argument("--audience", default="curieux du sujet, niveau intermédiaire")
    p.add_argument("--seconds", type=float, default=DEFAULT_TOTAL_SECONDS)
    p.add_argument(
        "--clip-target-seconds",
        type=float,
        default=DEFAULT_CLIP_TARGET_SECONDS,
        help="Cible de durée par petit clip (modular_assembly).",
    )
    p.add_argument(
        "--no-modular",
        action="store_true",
        help="Ne pas inclure modular_assembly dans le JSON.",
    )
    p.add_argument("-o", "--output", help="Fichier JSON de sortie")
    args = p.parse_args()

    brief = build_brief(args.domain, args.angle, audience=args.audience, total_seconds=args.seconds)
    text = brief.to_json(
        modular=not args.no_modular,
        clip_target_seconds=args.clip_target_seconds,
    )
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Écrit : {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
