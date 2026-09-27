"""Scene animation (P8-8): identity-stable multi-figure streams -> scene
actions.

Design of record: ``docs/SCENE_ANIMATION.md`` (written BEFORE this module —
the ROOT_MOTION.md sibling pattern). Closes ledger row L8 (single-character
video only): the P2-1 job container already carries per-frame multi-figure
payloads; what was missing is the IDENTITY layer — detector labels are
per-frame local and swap freely (the L8 wording), so per-frame
figure->character assignment runs by POSE-SIMILARITY cost (shape + body
scale — the two identity signals hips-anchoring preserves), solved with a
DETERMINISTIC rectangular assignment (Kuhn-Munkres, keyed order — no set
iteration anywhere), with a cost-jump SWAP ALARM (computed without ground
truth, loud in the product) and MANUAL OVERRIDES winning over everything
(the honesty law: suggest what is inferred, enforce what is authored).

Three pieces, all additive, nothing existing modified:

- :func:`assign_stream` — the per-frame identity pass. Returns a
  :class:`SceneAction` (the animation: per-frame
  :class:`~riggermortis.scene.ScenePose` keyed by CHARACTER, pins carried
  in authored order) plus an :class:`IdentityReport` (the honest ledgers:
  alarms, cost jumps, extras, overridden frames, solve-vs-authored
  disagreements, failed frames — gaps stay gaps, never interpolated).
- :func:`placements_for` / :func:`scene_reference` — per-frame in-plane
  placements MEASURED from the stream's detector bboxes (LABELED
  APPROXIMATE: single view cannot separate body size from distance; depth
  stays exactly zero, never guessed) — the coupling input. Per-frame
  coupling itself is P8-2's :func:`~riggermortis.coupling.couple_scene`,
  UNTOUCHED (D-016): see :func:`couple_scene_action`.
- :func:`track_for_character` / :meth:`SceneAction.actions_view` — the S32
  drift track per character (``track_from_payload_stream`` reused VERBATIM)
  and the decomposition into per-character
  :class:`~riggermortis.action.CanonicalAction`s — the exact input the
  CERTIFIED bake already consumes; the bake path itself is untouched.

Pure stdlib (D-003); deterministic (sorted keys on every output path);
errors are :class:`~riggermortis.errors.SceneError` (the scene domain's
bucket — no new error class). NOTHING here mutates its inputs (pinned by
test, the certified-composition discipline).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from .action import ActionFrame, CanonicalAction
from .canonical_pose import CanonicalPose
from .coupling import CoupleReport, Placement, couple_scene
from .errors import RiggermortisError, SceneError
from .payload import figure_entries
from .root_motion import DriftTrack, track_from_payload_stream
from .scene import ContactPin, SceneFigure, ScenePose
from .video import STATE_NAME, load_state

#: The identity cost's body-scale term weight (declared untuned, D-008):
#: ``|log(scale ratio)|`` — scale-free, and the identity evidence that
#: SURVIVES pose convergence (two bodies matching poses are still two
#: bodies; the detector's pixels-per-unit scale sees the difference).
SCALE_WEIGHT = 1.0

#: Below this many COMMON observed roles a pose pair is UNCOMPARABLE —
#: the pairing refuses loud, never a fabricated cost (the torso chain
#: plus both girdles is the minimum meaningful shape sample).
MIN_COMMON_ROLES = 6

#: The swap alarm's margins (declared untuned; the probe/gate publish BOTH
#: cost-jump distributions — authored swap events vs ordinary frames — and
#: the constants' place in the gap, the strike-S12 derivation pattern):
#: the continuation mapping must be worse by more than ALARM_ABS absolute
#: AND ALARM_REL relative for the alarm to fire (the relative guard keeps
#: near-zero-cost frames quiet; the absolute guard keeps noise quiet).
ALARM_ABS = 0.02
ALARM_REL = 0.25

#: How many frames around an authored identity event an alarm may land and
#: still COUNT as catching it (the probe/gate's GT rule; the alarm itself
#: is frame-exact — this is the measurement tolerance).
ALARM_HALO = 2

_UNCOMPARABLE = 1e9  # keeps the solve total; a chosen None pairing refuses


# -- the stream model -------------------------------------------------------------


@dataclass(frozen=True)
class StreamFigure:
    """One detected figure of one frame.

    ``label`` is the detector's PER-FRAME LOCAL label — unstable across
    frames, which is exactly why this module exists. ``pose`` is the FULL
    solved pose (hands/face/roll ride additively, D-021/D-022/D-023).
    ``bbox_center`` is the detector bbox center in pixels (from the
    payload entry's ``bbox``); None when absent — placements and tracks
    then report unavailable, never guess.
    """

    label: str
    pose: CanonicalPose
    bbox_center: tuple[float, float] | None = None


@dataclass(frozen=True)
class StreamFrame:
    """One frame's detected figures (label-sorted by the builders)."""

    frame: int
    figures: tuple[StreamFigure, ...]


def load_scene_frames(job_dir: Path) -> list[StreamFrame]:
    """A P2-1 job directory -> the multi-figure stream (D-009: payloads
    are parsed through :mod:`riggermortis.payload`; the state's ``done``
    map is the frame plan). Unreadable poses refuse with the frame named —
    never silently skipped (the loader's caller decides what a gap means;
    :func:`assign_stream` reports ITS gaps loudly too)."""
    job_dir = Path(job_dir)
    state = load_state(job_dir)
    if state is None:
        raise RiggermortisError(
            f"no video job state in {job_dir}",
            hint="run the job first: rigpose pose-video <frames_dir> "
                 f"<rig.json> --out {job_dir} (state file: {STATE_NAME})",
        )
    done: dict[int, str] = {
        int(k): str(v) for k, v in state.get("done", {}).items()}
    out: list[StreamFrame] = []
    for index in sorted(done):
        path = job_dir / done[index]
        if not path.exists():
            raise RiggermortisError(
                f"frame {index}: the state lists {done[index]} but the "
                "file is gone",
                hint="re-run the job or restore the payload — the stream "
                     "never fabricates a frame",
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise RiggermortisError(
                f"frame {index}: unreadable payload ({exc})",
                hint="re-run the job for this frame — the stream never "
                     "fabricates a frame",
            ) from exc
        figs: list[StreamFigure] = []
        for entry in figure_entries(payload):
            pose_d = entry.get("pose")
            if not isinstance(pose_d, dict):
                continue  # the caller's gap ledger sees the missing figure
            bbox = entry.get("bbox")
            center: tuple[float, float] | None = None
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                center = ((float(bbox[0]) + float(bbox[2])) / 2.0,
                          (float(bbox[1]) + float(bbox[3])) / 2.0)
            figs.append(StreamFigure(
                label=str(entry.get("label") or "figure 0"),
                pose=CanonicalPose.from_dict(pose_d),
                bbox_center=center,
            ))
        out.append(StreamFrame(
            frame=index,
            figures=tuple(sorted(figs, key=lambda f: f.label)),
        ))
    return out


# -- the deterministic assignment -------------------------------------------------


def hungarian(cost: list[list[float]]) -> list[int]:
    """Deterministic rectangular assignment (Kuhn-Munkres, O(n^3), stdlib).

    ``cost`` is rows x columns with rows <= columns; returns the column
    index assigned to each row (-1 for a row left unassigned, which the
    rectangular case never produces). The scan order is fixed by the
    matrix layout — every caller feeds rows/columns in SORTED order, so
    ties resolve deterministically (the keyed-sort law; no set iteration,
    no dict ordering in any output path).
    """
    n, m = len(cost), len(cost[0])
    inf = float("inf")
    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    match = [0] * (m + 1)  # match[j] = row assigned to column j (1-based)
    way = [0] * (m + 1)
    for i in range(1, n + 1):
        match[0] = i
        j0 = 0
        minv = [inf] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0 = match[j0]
            delta = inf
            j1 = 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(m + 1):
                if used[j]:
                    u[match[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if match[j0] == 0:
                break
        while True:
            j1 = way[j0]
            match[j0] = match[j1]
            j0 = j1
            if j0 == 0:
                break
    out = [-1] * n
    for j in range(1, m + 1):
        if match[j] != 0:
            out[match[j] - 1] = j - 1
    return out


def pose_cost(a: CanonicalPose, b: CanonicalPose) -> float | None:
    """The declared identity cost between two solved poses.

    ``mean position distance over COMMON observed roles + SCALE_WEIGHT *
    |log(scale ratio)|`` — positions are the one convention-free metric
    (the S23 lesson) and the scale term is the identity evidence that
    survives pose convergence. Returns None when the pair is UNCOMPARABLE
    (fewer than MIN_COMMON_ROLES common roles, or a non-positive scale):
    the caller refuses loud, never fabricates a cost.
    """
    common = sorted(set(a.positions) & set(b.positions))
    if len(common) < MIN_COMMON_ROLES:
        return None
    total = 0.0
    for role in common:
        total += math.dist(a.positions[role], b.positions[role])
    if a.scale <= 0.0 or b.scale <= 0.0:
        return None
    return total / len(common) + SCALE_WEIGHT * abs(math.log(b.scale / a.scale))


def _solve_matrix(
    prev: dict[str, CanonicalPose],
    figures: list[StreamFigure],
    characters: list[str],
) -> tuple[dict[str, str], dict[str, float]]:
    """The optimal character->figure assignment at one frame (sorted keys
    everywhere). More characters than figures: transpose + invert (each
    FIGURE gets a character; the leftover characters come back unassigned
    and the caller fails the frame loud). A chosen UNCOMPARABLE pairing
    refuses with a hint (never guessed)."""
    labels = [f.label for f in figures]  # the caller passes label-sorted
    by_label = {f.label: f for f in figures}
    rows = sorted(characters)
    cost_rows: list[list[float]] = []
    comparable: dict[tuple[str, str], bool] = {}
    for ch in rows:
        row: list[float] = []
        for lab in labels:
            c = pose_cost(prev[ch], by_label[lab].pose)
            comparable[(ch, lab)] = c is not None
            row.append(c if c is not None else _UNCOMPARABLE)
        cost_rows.append(row)
    if len(rows) <= len(labels):
        cols = hungarian(cost_rows)
    else:
        t_rows = [[cost_rows[r][c] for r in range(len(rows))]
                  for c in range(len(labels))]
        t_cols = hungarian(t_rows)
        cols = [-1] * len(rows)
        for r, c in enumerate(t_cols):
            if c >= 0:
                cols[c] = r
    assignment: dict[str, str] = {}
    costs: dict[str, float] = {}
    for r, ch in enumerate(rows):
        if cols[r] >= 0:
            lab = labels[cols[r]]
            assignment[ch] = lab
            costs[ch] = cost_rows[r][cols[r]]
    for ch in rows:
        lab = assignment.get(ch)
        if lab is not None and not comparable[(ch, lab)]:
            raise SceneError(
                f"uncomparable pairing: character {ch!r} assigned figure "
                f"{lab!r} with fewer than {MIN_COMMON_ROLES} common roles",
                hint="the detector saw too little of one figure to compare "
                     "identity — the frame is refused, never guessed",
            )
    return assignment, costs


def _continuation_cost(
    prev_pose: dict[str, CanonicalPose],
    prev_assignment: dict[str, str],
    figures: list[StreamFigure],
    characters: list[str],
) -> float | None:
    """The previous frame's mapping evaluated on THIS frame's costs — the
    evidence-alarm input (no ground truth needed). None = the continuation
    is not evaluable (a label vanished, or a pair is uncomparable)."""
    by_label = {f.label: f for f in figures}
    total = 0.0
    for ch in sorted(characters):
        lab = prev_assignment.get(ch)
        if lab is None or lab not in by_label:
            return None
        c = pose_cost(prev_pose[ch], by_label[lab].pose)
        if c is None:
            return None
        total += c
    return total


# -- the scene action + the identity report ---------------------------------------


@dataclass(frozen=True)
class SceneActionFrame:
    """One solved frame: a character-keyed scene + the assignment's provenance."""

    frame: int
    scene: ScenePose
    assignment: dict[str, str]
    costs: dict[str, float]
    overridden: bool


@dataclass
class SceneAction:
    """The scene animation: ordered frames + honest ledgers (the multi-
    figure counterpart of :class:`~riggermortis.action.CanonicalAction`).

    ``pins`` ride in AUTHORED order (the P8-2 contract) and are coupled
    PER FRAME (see :func:`couple_scene_action`). ``tracks`` carry the
    per-character drift track where the stream supplied bbox centers
    (S32, verbatim). ``actions_view`` decomposes into the per-character
    canonical actions the certified bake already consumes."""

    frames: list[SceneActionFrame] = field(default_factory=list)
    failed: list[int] = field(default_factory=list)
    characters: tuple[str, ...] = ()
    pins: tuple[ContactPin, ...] = ()
    tracks: dict[str, DriftTrack] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def frame_indices(self) -> list[int]:
        return [af.frame for af in self.frames]

    def actions_view(self) -> dict[str, CanonicalAction]:
        """The per-character canonical actions (sorted keys). The certified
        bake consumes these UNCHANGED — the scene action composes, never
        forks, the animation path."""
        out: dict[str, CanonicalAction] = {}
        for ch in sorted(self.characters):
            pairs = [(af.frame, scene_pose_of(af, ch))
                     for af in self.frames]
            out[ch] = CanonicalAction(
                frames=[ActionFrame(frame=f, pose=p) for f, p in pairs],
                failed=list(self.failed),
                notes=list(self.notes),
                root_track=self.tracks.get(ch),
            )
        return out


def scene_pose_of(frame: SceneActionFrame, character: str) -> CanonicalPose:
    """The frame's pose for one character (refuses with a hint when the
    character is not in the scene — never silently None)."""
    for fig in frame.scene.figures:
        if fig.label == character:
            return fig.pose
    raise SceneError(
        f"character {character!r} is not in this frame's scene",
        hint=f"characters here: "
             f"{', '.join(f.label for f in frame.scene.figures)}",
    )


@dataclass(frozen=True)
class SwapAlarm:
    """One alarm record — computed WITHOUT ground truth, loud in the product.

    ``kind='evidence'``: the previous frame's mapping is measurably worse
    on this frame than the chosen one (the identity evidence moved — the
    Annex bar's alarm). ``kind='flip'``: the solved assignment differs
    from the previous frame's (the observable discontinuity, reported as
    a ledger row; corrections and ambiguity both SHOW here).
    """

    frame: int
    kind: str
    detail: str


@dataclass
class IdentityReport:
    """The identity pass's honest ledgers (nothing silent anywhere)."""

    alarms: list[SwapAlarm] = field(default_factory=list)
    #: per solved frame with an evaluable continuation: (frame, abs, rel)
    jumps: list[tuple[int, float, float]] = field(default_factory=list)
    #: per frame where more figures than characters were detected
    extras: dict[int, list[str]] = field(default_factory=dict)
    overridden_frames: list[int] = field(default_factory=list)
    #: solve-vs-authored disagreements, verbatim (the override wins; the
    #: solve's opinion is recorded, never absorbed silently)
    disagreements: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def assign_stream(
    stream: list[StreamFrame],
    characters: tuple[str, ...] = (),
    overrides: dict[int, dict[str, str]] | None = None,
    pins: tuple[ContactPin, ...] = (),
) -> tuple[SceneAction, IdentityReport]:
    """The per-frame identity pass (the committed algorithm).

    ``characters``: the stable roster (sorted, validated); empty = the
    sorted figure labels of the first frame BECOME the roster (the
    deterministic default). The seed frame assigns in SORTED order (keyed
    — identity evidence starts accumulating from frame 2). Returns
    ``(scene action, identity report)``; the input stream is never mutated.

    Loud classes: an empty stream refuses; a frame with fewer figures than
    characters FAILS into the action's gap ledger (a missing character
    cannot animate that frame; gaps stay gaps); an override referencing an
    absent label fails the frame; extra figures are REPORTED (sorted) and
    stay unassigned; a chosen uncomparable pairing refuses with a hint.
    """
    if not stream:
        raise SceneError(
            "the stream is empty — no frame carries a detection",
            hint="identity is assigned per frame from observed figures; "
                 "an empty stream has nothing to assign",
        )
    overrides = overrides or {}
    roster = sorted(characters) if characters else \
        sorted(f.label for f in stream[0].figures)
    if not roster:
        raise SceneError(
            "the character roster is empty and the first frame carries no "
            "figures",
            hint="pass the roster explicitly or feed a stream whose first "
                 "frame carries detections",
        )
    action = SceneAction(
        characters=tuple(roster), pins=tuple(pins))
    report = IdentityReport()
    prev_assignment: dict[str, str] | None = None
    prev_pose: dict[str, CanonicalPose] | None = None
    for sf in stream:
        figures = sorted(sf.figures, key=lambda f: f.label)
        labels = [f.label for f in figures]
        if len(figures) < len(roster):
            action.failed.append(sf.frame)
            report.notes.append(
                f"frame {sf.frame}: {len(roster) - len(figures)} character(s) "
                f"missing from the detection ({len(figures)} figure(s) "
                "found) — frame failed, never interpolated")
            continue
        over = overrides.get(sf.frame, {})
        if any(lab not in labels for lab in over.values()):
            action.failed.append(sf.frame)
            report.notes.append(
                f"frame {sf.frame}: an override references a label absent "
                f"from this frame's detection {sorted(labels)} — frame "
                "failed (the authored word must reference an observed "
                "figure, never a guessed one)")
            continue
        if prev_pose is None:
            # the seed frame: identity is assigned in SORTED order (keyed,
            # deterministic — evidence starts accumulating from frame 2)
            chosen = dict(zip(roster, labels[: len(roster)], strict=True))
            costs = {ch: 0.0 for ch in roster}
        else:
            forced = dict(over)
            free_ch = [c for c in roster if c not in forced]
            free_lab = [lab for lab in labels
                        if lab not in forced.values()]
            if free_ch:
                sub_prev = {c: prev_pose[c] for c in free_ch}
                sub_figs = [f for f in figures if f.label in free_lab]
                chosen_sub, costs_sub = _solve_matrix(
                    sub_prev, sub_figs, free_ch)
                chosen = {**chosen_sub, **forced}
                costs = {**costs_sub, **{c: 0.0 for c in forced}}
            else:  # every character overridden: the solve has no say
                chosen = dict(forced)
                costs = {c: 0.0 for c in roster}
        if len(labels) > len(roster):
            report.extras[sf.frame] = sorted(
                lab for lab in labels if lab not in chosen.values())
            report.notes.append(
                f"frame {sf.frame}: unassigned extra figure(s) "
                f"{report.extras[sf.frame]} — reported, never dropped "
                "silently")
        # the evidence alarm (continuation vs chosen — no GT needed)
        cont: float | None = None
        if prev_assignment is not None and prev_pose is not None:
            cont = _continuation_cost(
                prev_pose, prev_assignment, figures, roster)
        chosen_total = sum(costs[ch] for ch in roster)
        if cont is not None:
            jump_abs = cont - chosen_total
            if chosen_total > 1e-12:
                jump_rel: float = jump_abs / chosen_total
            else:
                jump_rel = float("inf") if jump_abs > 1e-12 else 0.0
            report.jumps.append((sf.frame, jump_abs, jump_rel))
            if jump_abs > ALARM_ABS and jump_rel > ALARM_REL:
                report.alarms.append(SwapAlarm(
                    sf.frame, "evidence",
                    f"continuation {cont:.4f} vs chosen {chosen_total:.4f} "
                    f"(abs {jump_abs:.4f} > {ALARM_ABS}, rel "
                    f"{jump_rel:.2f} > {ALARM_REL}) — the identity evidence "
                    "moved: review this frame"))
        if prev_assignment is not None and chosen != prev_assignment:
            changed = sorted(
                c for c in roster
                if chosen.get(c) != prev_assignment.get(c))
            moves = {
                c: (prev_assignment.get(c), chosen.get(c)) for c in changed}
            report.alarms.append(SwapAlarm(
                sf.frame, "flip",
                f"assignment changed for {changed}: {moves}"))
        overridden = bool(over)
        if overridden:
            report.overridden_frames.append(sf.frame)
            # the solve-vs-authored comparison: what the FREE solve would
            # have said for this frame (unavailable when its matrix is
            # uncomparable — exactly the case overrides exist for)
            pure: dict[str, str] | None = None
            if prev_pose is not None:
                try:
                    pure, _pure_costs = _solve_matrix(
                        prev_pose, figures, roster)
                except SceneError:
                    pure = None
            for ch, lab in sorted(over.items()):
                solved_say = pure.get(ch) if pure else None
                if solved_say is not None and solved_say != lab:
                    report.disagreements.append(
                        f"frame {sf.frame}: character {ch!r} — solve said "
                        f"{solved_say!r}, the artist's override says "
                        f"{lab!r}; the override wins (authored > inferred)")
            chosen = {**chosen, **over}
        by_label = {f.label: f for f in figures}
        scene = ScenePose(
            name=f"sceneanim-{sf.frame}",
            figures=[
                SceneFigure(label=ch, pose=by_label[chosen[ch]].pose)
                for ch in roster
            ],
            pins=list(pins),
        )
        action.frames.append(SceneActionFrame(
            frame=sf.frame, scene=scene,
            assignment=dict(chosen), costs=dict(costs),
            overridden=overridden,
        ))
        prev_assignment = dict(chosen)
        prev_pose = {ch: by_label[chosen[ch]].pose for ch in roster}
    action.notes.extend(report.notes)
    return action, report


# -- the per-frame scene pass (placements + coupling) ------------------------------


def scene_reference(
    stream: list[StreamFrame],
    assignment_of: dict[int, dict[str, str]],
) -> tuple[tuple[float, float], float]:
    """The placements' SHARED scene origin: the first frame where every
    roster character is present WITH a bbox center contributes (a) its
    minimum-label character's bbox center — the origin every figure's
    translation is measured against, so the figures keep their real
    separation in scene space — and (b) that character's ``scale`` as the
    scene unit ``U`` (px per canonical unit; one deterministic constant).
    Refuses loud when no such frame exists."""
    for sf in stream:
        assignment = assignment_of.get(sf.frame)
        if not assignment:
            continue
        by_label = {f.label: f for f in sf.figures}
        centers: dict[str, tuple[float, float]] = {}
        for ch in sorted(assignment):
            fig = by_label.get(assignment[ch])
            if fig is None or fig.bbox_center is None:
                centers = {}
                break
            centers[ch] = fig.bbox_center
        if centers:
            anchor_ch = min(centers)
            unit = by_label[assignment[anchor_ch]].pose.scale
            if unit <= 0.0:
                raise SceneError(
                    f"frame {sf.frame}: the reference character's scale is "
                    f"{unit!r} — the scene unit must be positive",
                    hint="the payload solve carries the pixels-per-unit "
                         "scale; a non-positive one is a broken solve",
                )
            return centers[anchor_ch], unit
    raise SceneError(
        "no frame carries every character's bbox center — the placements "
        "have no reference",
        hint="placements are MEASURED from the detector bboxes; a stream "
             "without them stages no scene (nothing is guessed)",
    )


def placements_for(
    assignment: dict[str, str],
    figures: list[StreamFigure],
    ref: tuple[tuple[float, float], float],
) -> dict[str, Placement]:
    """Per-frame in-plane placements MEASURED from the stream (the declared
    APPROXIMATE model, docs/SCENE_ANIMATION.md).

    ``t = ((cx − o_x)/U, 0.0, −(cy − o_y)/U)`` against the SHARED scene
    origin ``o`` (the reference frame's anchor center — figures keep their
    real separation), pixel v-down vs canonical z-up (the ROOT_MOTION sign
    convention); ``s = figure_scale / U`` — apparent-size staging;
    ``dy = 0.0`` EXACTLY (depth unobservable from a single view — never
    guessed). A figure without a bbox center refuses loud (placements are
    measured, never fabricated)."""
    origin, unit = ref
    by_label = {f.label: f for f in figures}
    out: dict[str, Placement] = {}
    for ch in sorted(assignment):
        fig = by_label.get(assignment[ch])
        if fig is None:
            raise SceneError(
                f"placement: figure {assignment[ch]!r} (character {ch!r}) "
                "is not in this frame",
                hint="the assignment and the frame disagree — rebuild the "
                     "scene action",
            )
        if fig.bbox_center is None:
            raise SceneError(
                f"placement: figure {fig.label!r} carries no bbox center",
                hint="placements come from the detector bbox; without it "
                     "the figure stages nowhere (nothing is guessed)",
            )
        c = fig.bbox_center
        s = fig.pose.scale
        if s <= 0.0:
            raise SceneError(
                f"placement: figure {fig.label!r} carries a non-positive "
                f"scale {s!r}",
                hint="the payload solve carries the pixels-per-unit scale",
            )
        t = ((c[0] - origin[0]) / unit, 0.0, -(c[1] - origin[1]) / unit)
        out[ch] = Placement(quat=(1.0, 0.0, 0.0, 0.0), t=t, s=s / unit)
    return out


def couple_scene_action(
    action: SceneAction,
    stream: list[StreamFrame],
) -> list[tuple[int, ScenePose, CoupleReport]]:
    """The per-frame scene pass: MEASURED placements + P8-2's UNTOUCHED
    :func:`~riggermortis.coupling.couple_scene`, frame by frame.

    Returns ``(frame, coupled scene, report)`` for every solved frame in
    order. Frames without enforceable pins pass through byte-identically
    (the zero-pins contract); beyond-reach pins stay LOUD in their report
    (the P8-2 REACH honesty, per frame). Pure: the action and the stream
    are never mutated."""
    assignment_of = {af.frame: af.assignment for af in action.frames}
    figures_of = {sf.frame: list(sf.figures) for sf in stream}
    ref = scene_reference(stream, assignment_of)
    out: list[tuple[int, ScenePose, CoupleReport]] = []
    for af in action.frames:
        pl = placements_for(af.assignment, figures_of[af.frame], ref)
        _coupled, report = couple_scene(af.scene, pl)
        out.append((af.frame, _coupled, report))
    return out


# -- the S32 drift track, per character --------------------------------------------


def track_for_character(
    stream: list[StreamFrame],
    assignment_of: dict[int, dict[str, str]],
    character: str,
) -> DriftTrack | None:
    """The character's drift track from the ASSIGNED figure's bbox stream —
    S32's :func:`~riggermortis.root_motion.track_from_payload_stream`,
    reused VERBATIM (D-016). In-plane only, LABELED approximate, depth
    exactly zero. Returns None (loudly noted by the caller) when any
    assigned frame lacks a bbox center — a PARTIAL track would fabricate
    speed discontinuities, so no track ships instead."""
    entries: list[tuple[int, float, float, float]] = []
    for sf in stream:
        assignment = assignment_of.get(sf.frame)
        if not assignment or character not in assignment:
            continue
        by_label = {f.label: f for f in sf.figures}
        fig = by_label.get(assignment[character])
        if fig is None or fig.bbox_center is None:
            return None
        entries.append((
            sf.frame, fig.bbox_center[0], fig.bbox_center[1],
            fig.pose.scale,
        ))
    if not entries:
        return None
    return track_from_payload_stream(entries)


def attach_tracks(
    action: SceneAction, stream: list[StreamFrame],
) -> SceneAction:
    """Build + attach every character's drift track (None-absent stays
    absent — the byte-identity of a track-free action is preserved)."""
    assignment_of = {af.frame: af.assignment for af in action.frames}
    tracks: dict[str, DriftTrack] = {}
    notes = list(action.notes)
    for ch in action.characters:
        t = track_for_character(stream, assignment_of, ch)
        if t is not None:
            tracks[ch] = t
        else:
            notes.append(
                f"character {ch!r}: no drift track — the assigned frames "
                "do not all carry bbox centers (nothing was guessed)")
    return SceneAction(
        frames=list(action.frames),
        failed=list(action.failed),
        characters=action.characters,
        pins=action.pins,
        tracks=tracks,
        notes=notes,
    )
