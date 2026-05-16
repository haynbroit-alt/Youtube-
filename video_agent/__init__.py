"""Video production planning utilities."""

from typing import TYPE_CHECKING

__all__ = ["ProductionBrief", "build_brief"]

if TYPE_CHECKING:
    from video_agent.planner import ProductionBrief, build_brief


def __getattr__(name: str):
    if name in __all__:
        from video_agent import planner

        return getattr(planner, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
