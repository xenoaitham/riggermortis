"""P1-3 tests: figure board ordering + selection (stdlib-only)."""
from __future__ import annotations

from riggermortis.inference.figures import FigureBoard
from riggermortis.inference.poses import Detection, Figure


def _det() -> Detection:
    figs = [
        Figure(index=0, bbox=(400, 0, 500, 300), score=0.8,
               keypoints=[(1.0, 1.0)] * 133, confidences=[0.5] * 133),
        Figure(index=1, bbox=(10, 0, 210, 400), score=0.9,
               keypoints=[(1.0, 1.0)] * 133, confidences=[0.5] * 133),
        Figure(index=2, bbox=(220, 0, 320, 380), score=0.9,
               keypoints=[(1.0, 1.0)] * 133, confidences=[0.5] * 133),
    ]
    return Detection(width=640, height=480, figures=figs)


def test_stable_ordering_and_labels() -> None:
    board = FigureBoard.from_detection(_det())
    # score desc, then leftmost: figure 1 (x=10) before figure 2 (x=220), then 0.
    assert board.labels() == ["figure 1", "figure 2", "figure 3"]
    assert board.figures[0].bbox[0] == 10.0
    # Rebuilding yields identical labels (deterministic).
    board2 = FigureBoard.from_detection(_det())
    assert board2.labels() == board.labels()


def test_selection_vocabulary() -> None:
    board = FigureBoard.from_detection(_det())
    assert board.primary() is board.figures[0]
    # Largest bbox: figure 1 spans 200x400 = 80000, the biggest.
    assert board.largest() is board.figures[0]
    assert board.select("figure 2") is board.figures[1]
    assert board.select(2) is board.figures[2]
    assert board.select(99) is None
    assert board.select("figure 99") is None


def test_empty_detection() -> None:
    board = FigureBoard.from_detection(Detection(width=10, height=10, figures=[]))
    assert board.primary() is None
    assert board.largest() is None
    assert board.labels() == []
    assert board.summary() == {"count": 0, "labels": [], "boxes": [], "scores": []}
