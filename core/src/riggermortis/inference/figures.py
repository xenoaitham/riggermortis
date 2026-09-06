"""Multi-figure selection: stable labels and a selection API for the UI.

Wraps a :class:`riggermortis.inference.poses.Detection` with the deterministic
figure order (score desc, then leftmost, then topmost) and the small
selection vocabulary the add-on and MCP tools expose: by stable label, by
largest bbox area, or the primary (best-scoring) figure. Pure stdlib.
"""
from __future__ import annotations

from dataclasses import dataclass

from .poses import Detection, Figure


@dataclass
class FigureBoard:
    """Detection figures with stable, deterministic labels and selection."""

    figures: list[Figure]  # deterministic order, index == position in list

    @classmethod
    def from_detection(cls, detection: Detection) -> FigureBoard:
        ordered = detection.sorted_figures()
        for i, fig in enumerate(ordered):
            fig.label = f"figure {i + 1}"
        return cls(figures=ordered)

    def labels(self) -> list[str]:
        return [f.label for f in self.figures]

    def primary(self) -> Figure | None:
        """Best-scoring figure, or None when nothing was detected."""
        return self.figures[0] if self.figures else None

    def largest(self) -> Figure | None:
        """Figure with the largest bbox area (ties: board order)."""
        if not self.figures:
            return None
        return max(self.figures, key=lambda f: ((f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), -f.index))

    def select(self, key: str | int) -> Figure | None:
        """Select by stable label ("figure 2") or 0-based board index."""
        if isinstance(key, int):
            if 0 <= key < len(self.figures):
                return self.figures[key]
            return None
        for fig in self.figures:
            if fig.label == key:
                return fig
        return None

    def summary(self) -> dict[str, object]:
        return {
            "count": len(self.figures),
            "labels": self.labels(),
            "boxes": [[round(v, 1) for v in f.bbox] for f in self.figures],
            "scores": [round(f.score, 3) for f in self.figures],
        }
