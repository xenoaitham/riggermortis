"""Secondary motion (P6-1): damped spring chains over canonical roles.

Design of record: docs/SECONDARY_MOTION.md. A chain is a sequence of rigid
links (directions only — length is free in direction space) hanging off a
canonical role's bone; each link is a damped angular spring pulled toward a
rest direction authored in its parent frame, so the chain inherits anchor
rotation through the springs and curvature propagates down the links. The
output is a per-frame track of unit world directions; the add-on bakes it
onto real appendage bones via the ``secondary`` binding on ``bake_action``.

The simulation rides AFTER the certified composition (stabilize → smooth →
reduce → detect → lock): it READS the locked action, never mutates it, and
cannot reorder or weaken the foot-lock guarantee (contacts/lock own the leg
roles; this module writes nothing back). D-008: every constant is an
order-of-magnitude default declared untuned — the gate asserts behavior
(follow, lag, settle, determinism), never trajectory values.

Determinism: semi-implicit Euler at a fixed integer substep count per
frame, pure float math, chains iterated in sorted-name order, no wall-clock
input anywhere. Frames are consecutive observations — a gap from a failed
frame shortens the series instead of fabricating in-betweens (the
conditioning convention).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .action import CanonicalAction
from .canonical import CANONICAL, PRIMARY_CHILD
from .errors import SecondaryError
from .linalg import Vec3, v_add, v_cross, v_dot, v_len, v_norm, v_scale, v_sub

#: Integration target: ω·dt ≈ 0.08 at the default 3 Hz — two orders inside
#: the semi-implicit Euler stability bound (ω·dt < 2). D-008: untuned.
DT_TARGET = 1.0 / 240.0
#: Hair/tail on a ~1.7 m figure swings at single-digit Hz; 3 Hz mid-band.
DEFAULT_FREQ_HZ = 3.0
#: Underdamped enough to show follow-through, settles in a few swings.
DEFAULT_DAMPING_RATIO = 0.5

FREQ_BAND = (0.1, 20.0)
DAMPING_BAND = (0.0, 5.0)  # 0 refused — a chain that never settles is a bug
LINKS_MIN, LINKS_MAX = 1, 16

_SCHEMA_FIELDS = frozenset(
    {
        "format",
        "name",
        "anchor_role",
        "links",
        "rest_direction",
        "rest_directions",
        "freq_hz",
        "damping_ratio",
    }
)


def _spec(message: str, hint: str) -> SecondaryError:
    return SecondaryError(message, hint=hint or None)


@dataclass(frozen=True)
class ChainSpec:
    """One validated spring chain (directions-only v1 schema, format 1)."""

    name: str
    anchor_role: str
    links: int
    rest_directions: tuple[Vec3, ...]
    freq_hz: float = DEFAULT_FREQ_HZ
    damping_ratio: float = DEFAULT_DAMPING_RATIO

    def to_dict(self) -> dict[str, object]:
        dirs = self.rest_directions
        d: dict[str, object] = {
            "format": 1,
            "name": self.name,
            "anchor_role": self.anchor_role,
            "links": self.links,
            "freq_hz": self.freq_hz,
            "damping_ratio": self.damping_ratio,
        }
        if all(r == dirs[0] for r in dirs):
            d["rest_direction"] = list(dirs[0])
        else:
            d["rest_directions"] = [list(r) for r in dirs]
        return d

    @classmethod
    def from_dict(cls, d: object) -> ChainSpec:
        """Validate loudly: unknown fields, bad bands, and unknown roles all
        refuse with an actionable hint (the style-presets discipline)."""
        if not isinstance(d, dict):
            raise _spec("chain spec must be a JSON object", "got a non-object payload")
        unknown = sorted(set(d) - _SCHEMA_FIELDS)
        if unknown:
            raise _spec(
                f"chain spec has unknown field(s): {', '.join(unknown)}",
                f"known fields: {', '.join(sorted(_SCHEMA_FIELDS))}",
            )
        fmt = d.get("format", 1)
        if fmt != 1:
            raise _spec(
                f"unsupported chain spec format {fmt!r}", "this build reads format 1"
            )
        name = d.get("name")
        if not isinstance(name, str) or not name:
            raise _spec("chain spec needs a non-empty 'name'", "e.g. 'tail'")
        role = d.get("anchor_role")
        if not isinstance(role, str) or role not in CANONICAL:
            raise _spec(
                f"chain {name!r}: unknown anchor_role {role!r}",
                "any canonical role name, e.g. 'hips', 'head', 'chest'",
            )
        if CANONICAL[role].parent is None:
            raise _spec(
                f"chain {name!r}: anchor_role 'root' has no parent bone",
                "chains need a parent direction — use hips, spine, chest, "
                "neck, head, or a limb role",
            )
        links = d.get("links")
        if not isinstance(links, int) or isinstance(links, bool) or not (
            LINKS_MIN <= links <= LINKS_MAX
        ):
            raise _spec(
                f"chain {name!r}: links must be an int in "
                f"[{LINKS_MIN}, {LINKS_MAX}], got {links!r}",
                "a hair strand or tail is typically 3-8 links in v1",
            )
        raw_dirs = _rest_directions(name, d, links)
        freq = d.get("freq_hz", DEFAULT_FREQ_HZ)
        damping = d.get("damping_ratio", DEFAULT_DAMPING_RATIO)
        for label, val, band in (
            ("freq_hz", freq, FREQ_BAND),
            ("damping_ratio", damping, DAMPING_BAND),
        ):
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                raise _spec(
                    f"chain {name!r}: {label} must be a number, got {val!r}", ""
                )
            if not band[0] <= float(val) <= band[1]:
                raise _spec(
                    f"chain {name!r}: {label}={val!r} outside the schema band "
                    f"{band[0]}..{band[1]}",
                    "bands are validation rails, not physics claims (D-008)",
                )
        if float(damping) <= 0.0:
            raise _spec(
                f"chain {name!r}: damping_ratio must be > 0",
                "a chain that never settles is a bug, not a style",
            )
        return cls(
            name=name,
            anchor_role=role,
            links=links,
            rest_directions=raw_dirs,
            freq_hz=float(freq),
            damping_ratio=float(damping),
        )


def _rest_directions(
    name: str, d: dict[str, object], links: int
) -> tuple[Vec3, ...]:
    """Read ``rest_direction`` (one triple for every link) or per-link
    ``rest_directions``; normalized, zero-length refused."""
    per_link = d.get("rest_directions")
    if per_link is not None:
        if not isinstance(per_link, (list, tuple)) or len(per_link) != links:
            raise _spec(
                f"chain {name!r}: rest_directions must list exactly {links} "
                f"triple(s) for {links} link(s)",
                "or give a single 'rest_direction' shared by every link",
            )
        raw = list(per_link)
    else:
        single = d.get("rest_direction", (0.0, 0.0, -1.0))
        raw = [single] * links
    normed: list[Vec3] = []
    for i, v in enumerate(raw):
        if (
            not isinstance(v, (list, tuple))
            or len(v) != 3
            or not all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in v)
        ):
            raise _spec(
                f"chain {name!r}: rest direction {i} is not an XYZ triple",
                f"got {v!r}",
            )
        vec = (float(v[0]), float(v[1]), float(v[2]))
        ln = v_len(vec)
        if ln < 1e-9:
            raise _spec(
                f"chain {name!r}: rest direction {i} is zero-length",
                "point it somewhere: straight down is [0.0, 0.0, -1.0]",
            )
        # already-unit vectors pass through unchanged so to_dict/from_dict
        # round-trips stay exact
        normed.append(vec if abs(ln - 1.0) < 1e-12 else v_norm(vec))
    return tuple(normed)


@dataclass(frozen=True)
class SecondaryTrack:
    """Per-frame unit world directions for one chain (aligned to ``frames``)."""

    name: str
    anchor_role: str
    frames: tuple[int, ...]
    directions: tuple[tuple[Vec3, ...], ...]


@dataclass
class SecondaryReport:
    """Honest sim metadata: behavior numbers, never trajectory claims."""

    chains: list[str] = field(default_factory=list)
    frames: int = 0
    substeps_per_frame: int = 0
    max_dev_deg: dict[str, float] = field(default_factory=dict)
    end_res_deg: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


Frame = tuple[Vec3, Vec3, Vec3]


def frame_from_dir(
    u: Vec3, side_ref: Vec3 = (1.0, 0.0, 0.0), fwd_ref: Vec3 = (0.0, -1.0, 0.0)
) -> Frame:
    """Right-handed parent frame: X = orthogonalized side ref, Y = along-bone
    ``u``, Z = X × Y. For an upright spine bone (Y≈+Z) the frame is exactly
    (character-left, up, character-back)."""
    y = v_norm(u)
    ref = side_ref if abs(v_dot(y, side_ref)) < 0.95 else fwd_ref
    d = v_dot(ref, y)
    x = v_norm((ref[0] - y[0] * d, ref[1] - y[1] * d, ref[2] - y[2] * d))
    return x, y, v_cross(x, y)


def _apply(f: Frame, v: Vec3) -> Vec3:
    """Frame columns times vector: ``v.x * X + v.y * Y + v.z * Z``."""
    return (
        v[0] * f[0][0] + v[1] * f[1][0] + v[2] * f[2][0],
        v[0] * f[0][1] + v[1] * f[1][1] + v[2] * f[2][1],
        v[0] * f[0][2] + v[1] * f[1][2] + v[2] * f[2][2],
    )


def _rotate(v: Vec3, axis: Vec3, angle: float) -> Vec3:
    """Rodrigues rotation (``axis`` must be unit)."""
    c, s = math.cos(angle), math.sin(angle)
    return v_norm(
        v_add(
            v_add(v_scale(v, c), v_scale(v_cross(axis, v), s)),
            v_scale(axis, v_dot(axis, v) * (1.0 - c)),
        )
    )


def _anchor_dir(positions: dict[str, Vec3], anchor_role: str) -> Vec3 | None:
    """Unit direction of the anchor bone from this frame's joint positions;
    None when the pose cannot orient it (missing roles / coincident joints).

    Orientation falls back to the primary child when the parent joint is
    coincident — root and hips share a joint in the canonical rest skeleton,
    so hips orients as hips→spine (still exactly the bone's up direction).
    """
    d: Vec3 | None = None
    parent = CANONICAL[anchor_role].parent
    if anchor_role in positions and parent in positions:
        d = v_sub(positions[anchor_role], positions[parent])
    if d is None or v_len(d) < 1e-9:
        child = PRIMARY_CHILD.get(anchor_role)
        if child and child in positions and anchor_role in positions:
            d = v_sub(positions[child], positions[anchor_role])
    if d is None or v_len(d) < 1e-9:
        return None
    return v_norm(d)


def _dev_deg(d: Vec3, target: Vec3) -> float:
    return math.degrees(math.atan2(v_len(v_cross(d, target)), v_dot(d, target)))


def simulate_secondary(
    action: CanonicalAction,
    chains: list[ChainSpec],
    *,
    fps: float,
) -> tuple[dict[str, SecondaryTrack], SecondaryReport]:
    """Simulate every chain over the (already-certified) action's frames.

    Returns one :class:`SecondaryTrack` per chain (dict keyed in sorted-name
    order) plus a :class:`SecondaryReport`. The action is never mutated;
    frames are consecutive observations (a gap shortens the series — never
    interpolated); each observed frame advances the integrator by an integer
    substep count so any fps stays exactly frame-aligned.
    """
    if not fps or fps <= 0:
        raise SecondaryError(
            f"fps must be positive, got {fps!r}",
            "the bake plays canonical frames at the source video's frame rate",
        )
    names = sorted(c.name for c in chains)
    if len(set(names)) != len(names):
        dupes = sorted({n for n in names if names.count(n) > 1})
        raise SecondaryError(
            f"duplicate chain name(s): {', '.join(dupes)}",
            "chain names key the output tracks — they must be unique",
        )
    by_name = {c.name: c for c in chains}
    report = SecondaryReport(
        chains=names,
        substeps_per_frame=max(1, math.ceil((1.0 / fps) / DT_TARGET)),
    )
    frames = sorted(action.frames, key=lambda af: af.frame)
    if not frames:
        report.notes.append("secondary: empty action — tracks are empty")
        return {}, report
    dt = (1.0 / fps) / report.substeps_per_frame
    omegas = {
        n: 2.0 * math.pi * by_name[n].freq_hz for n in names
    }
    dirs_state: dict[str, list[Vec3]] = {n: [] for n in names}
    w_state: dict[str, list[Vec3]] = {n: [] for n in names}
    rec_frames: dict[str, list[int]] = {n: [] for n in names}
    rec_dirs: dict[str, list[tuple[Vec3, ...]]] = {n: [] for n in names}
    dev_acc: dict[str, list[float]] = {n: [] for n in names}
    held: dict[str, int] = {n: 0 for n in names}
    unstarted: dict[str, int] = {n: 0 for n in names}
    notes: set[str] = set()

    for af in frames:
        a_dirs = {
            name: _anchor_dir(af.pose.positions, by_name[name].anchor_role)
            for name in names
        }
        for name in names:
            spec = by_name[name]
            dirs = dirs_state[name]
            w = w_state[name]
            a = a_dirs[name]
            if a is None:
                if dirs:
                    # chain already running: hold the state, record it (the
                    # bake's constant interpolation, honestly keyed)
                    held[name] += 1
                    rec_frames[name].append(af.frame)
                    rec_dirs[name].append(tuple(dirs))
                else:
                    unstarted[name] += 1
                continue
            k = omegas[name] ** 2
            c = 2.0 * spec.damping_ratio * omegas[name]
            for _ in range(report.substeps_per_frame):
                for i in range(spec.links):
                    parent_f = frame_from_dir(a) if i == 0 else frame_from_dir(dirs[i - 1])
                    target = _apply(parent_f, spec.rest_directions[i])
                    if i >= len(dirs):
                        dirs.append(target)  # chain starts at rest
                    d = dirs[i]
                    axis = v_cross(d, target)
                    w_old = w[i] if i < len(w) else (0.0, 0.0, 0.0)
                    accel = v_add(v_scale(axis, k), v_scale(w_old, -c))
                    w_i = v_add(w_old, v_scale(accel, dt))
                    if i < len(w):
                        w[i] = w_i
                    else:
                        w.append(w_i)
                    wl = v_len(w_i)
                    if wl > 1e-12:
                        d = _rotate(d, v_scale(w_i, 1.0 / wl), wl * dt)
                    dirs[i] = d
            rec_frames[name].append(af.frame)
            rec_dirs[name].append(tuple(dirs))
            # behavior metric: deviation from the instantaneous rest target
            for i, d in enumerate(dirs):
                parent_f = frame_from_dir(a) if i == 0 else frame_from_dir(dirs[i - 1])
                dev_acc[name].append(_dev_deg(d, _apply(parent_f, spec.rest_directions[i])))

    out: dict[str, SecondaryTrack] = {}
    for name in names:
        if rec_frames[name]:
            out[name] = SecondaryTrack(
                name=name,
                anchor_role=by_name[name].anchor_role,
                frames=tuple(rec_frames[name]),
                directions=tuple(rec_dirs[name]),
            )
        else:
            report.max_dev_deg[name] = 180.0
            report.end_res_deg[name] = 180.0
        if dev_acc[name]:
            report.max_dev_deg[name] = max(dev_acc[name])
            report.end_res_deg[name] = dev_acc[name][-1]
    report.frames = len(frames)
    for name in names:
        if unstarted[name]:
            report.notes.append(
                f"secondary {name}: {unstarted[name]} frame(s) could not "
                f"orient {by_name[name].anchor_role} — chain never started"
            )
        if held[name]:
            report.notes.append(
                f"secondary {name}: {held[name]} frame(s) could not "
                f"orient {by_name[name].anchor_role} — chain held"
            )
    report.notes.extend(sorted(notes))
    return out, report
