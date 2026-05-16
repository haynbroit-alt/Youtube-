"""
Planificateur de contenu long format (~10 minutes).
Produit une structure exploitable par des outils externes (LLM, TTS, éditeur).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


DEFAULT_TOTAL_SECONDS = 600  # 10 minutes


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
class ProductionBrief:
    domain: str
    angle: str
    audience: str
    total_seconds: float
    chapters: list[Chapter]
    hook_opening: str
    cta_closing: str
    seo_keywords: list[str]

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def to_dict(self) -> dict[str, Any]:
        def chapter_dict(c: Chapter) -> dict[str, Any]:
            d = asdict(c)
            d["beats"] = [asdict(b) for b in c.beats]
            return d

        return {
            "domain": self.domain,
            "angle": self.angle,
            "audience": self.audience,
            "total_seconds": self.total_seconds,
            "chapters": [chapter_dict(c) for c in self.chapters],
            "hook_opening": self.hook_opening,
            "cta_closing": self.cta_closing,
            "seo_keywords": self.seo_keywords,
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
    Construit un brief de ~10 minutes à partir d'un domaine et d'un angle éditorial.

    Ce n'est pas la vidéo elle-même : c'est le plan que votre pipeline
    (LLM, voix, montage) peut remplir et affiner.
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

    hook = (
        f"En 10 minutes : ce que « {domain} » change pour vous, "
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
    p.add_argument("-o", "--output", help="Fichier JSON de sortie")
    args = p.parse_args()

    brief = build_brief(args.domain, args.angle, audience=args.audience, total_seconds=args.seconds)
    text = brief.to_json()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Écrit : {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
