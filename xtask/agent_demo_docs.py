#!/usr/bin/env python3
"""Assemble the P3-7 agent-demo docs block (docs/AGENT_DEMO.md + transcript).

Runs in the user's shell AFTER a successful demo pass; every number it writes
travels via environment variables from ``xtask/agent_demo.sh`` — values read
directly from the actual run's JSON-RPC results, never hand-typed. The raw
agent/server transcript is copied verbatim next to the doc so every claim
cites the exchange that produced it.

    python3 xtask/agent_demo_docs.py --transcript-out docs/agent_demo_transcript.txt

Output paths are confined to the current directory or the temp dir; ``..``
segments are refused (same rule as the other edge scripts).
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

DEMO = "P3-7 E2E agent demo"


def _safe_out(raw: str) -> Path:
    path = Path(raw).expanduser()
    if any(part == os.pardir for part in path.parts):
        raise SystemExit(f"error: path must not contain {os.pardir!r}: {raw}")
    resolved = path.resolve()
    allowed = [Path.cwd().resolve(), Path(tempfile.gettempdir()).resolve()]
    if not any(resolved == base or base in resolved.parents for base in allowed):
        raise SystemExit(
            f"error: path must be inside the current directory or the temp dir: {raw}"
        )
    return resolved


def _env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"error: {name} is required (set by agent_demo.sh)")
    return value


def _deg(name: str) -> str:
    """A degree value from the run, rounded for display (full precision
    stays in the gate output)."""
    return f"{float(_env(name)):.4f}"


def main() -> int:
    transcript_src = Path(_env("DEMO_TRANSCRIPT_SRC"))
    manifest_src = Path(_env("DEMO_MANIFEST_SRC"))
    gif = _env("DEMO_GIF")
    # Links are relative to the DOC (docs/), not the repo root.
    gif_rel = gif.split("/")[-1]
    transcript_out = _safe_out(
        os.environ.get(
            "DEMO_TRANSCRIPT_OUT",
            "docs/agent_demo_transcript.txt",
        )
    )

    if not transcript_src.is_file():
        raise SystemExit(f"error: transcript missing: {transcript_src}")
    if not manifest_src.is_file():
        raise SystemExit(f"error: turntable manifest missing: {manifest_src}")
    transcript_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(transcript_src, transcript_out)

    rows = [
        ("what is this rig?", "`inspect_rig`",
         f"{_env('DEMO_ROLES')} roles mapped, min confidence {_env('DEMO_MIN_CONF')}"),
        ("what is live right now?", "`enqueue_action` -> `inspect_scene`",
         "armature inventoried inside Blender"),
        ("pose it from the photo", "`enqueue_action` -> `apply_pose`",
         f"{_env('DEMO_APPLY_BONES')} bones applied, self-check worst "
         f"{_deg('DEMO_APPLY_WORST')} deg"),
        ("animate from the video job", "`animate_from_video`",
         f"{_env('DEMO_CANON_FRAMES')} canonical frames, foot slide "
         f"{_env('DEMO_SLIDE_BEFORE')} -> {_env('DEMO_SLIDE_AFTER')} u; bake "
         "routed to the session action"),
        ("bake it on the rig", "`enqueue_action` -> `bake_action`",
         f"{_env('DEMO_BAKE_KEYS')} keys, {_env('DEMO_BAKE_LOCKED')} locked "
         f"frames, re-eval {_deg('DEMO_BAKE_REEVAL')} deg (lock dev "
         f"{_deg('DEMO_BAKE_LOCKDEV')} deg, {_env('DEMO_BAKE_INTERVALS')} "
         "contact intervals)"),
        ("show me", "`enqueue_action` -> `render_turntable`",
         f"{_env('DEMO_RENDERED')} orbit frames rendered, playing the baked "
         "action"),
    ]
    table = (
        "| the agent asks | through | answer (from the run) |\n"
        "|---|---|---|\n"
        + "\n".join("| " + " | ".join(cells) + " |" for cells in rows)
    )

    doc = f"""# Agent demo — one MCP conversation, zero human Blender interaction

Phase-3 gate asset ({DEMO}). A scripted agent owns the riggermortis MCP
server's stdio and drives a LIVE Blender through the whole loop:

```
agent --stdio--> MCP server --loopback 127.0.0.1--> Blender add-on (headless)
                                     (session bridge, token auth)
```

![agent-driven turntable]({gif_rel})

## The conversation

{table}

The verbatim exchange (requests `>>>`, responses `<<<`, progress
notifications included) is committed next to this file:
[{transcript_out.name}]({transcript_out.name}).

## What is real, and what is labeled

- **Real:** the protocol (newline-delimited JSON-RPC 2.0 over stdio, the
  session bridge over 127.0.0.1 with token auth), the rig (the local Rigify
  metarig), the pose payload (real `rigpose pose` pipeline output), every
  execution path (the add-on's real payload apply, bake, and render staging),
  and every number above (they traveled from the run's results).
- **Labeled SYNTHETIC:** the MOTION. The animate step consumes the walk
  fixture job serialized from the published generator
  (`xtask/walk_job.py` -> `xtask/hip_stab_gate.py build_walk`) — the same
  labeled synthetic walk behind every published lock number. The real-clip
  half of Phase 2 stays NEEDS-HUMAN (`out/video_smoke/SOURCES.md`); a real
  clip re-runs this demo unchanged.
- **Agent honesty:** the "agent" is a deterministic shell JSON-RPC client
  (`xtask/agent_demo.sh`) — a real MCP client speaking the real protocol,
  not an LLM improvising and not a human. Root motion is never baked (the
  single-view solve is hip-anchored; walk-in-place is the accepted baseline).

## Reproduce

```console
$ BLENDER=/path/to/blender PY=/path/to/python make agent-demo
```

Needs the local git-ignored assets (`out/real_rigs/metarig.blend`,
`out/payloads/metarig_payload.json` — see docs/BENCHMARKS.md). The gate that
keeps this honest in CI is `make session-verify` (self-contained: fixture
rig + fixture job, bake re-eval bar 0.5 deg).
"""
    doc_path = _safe_out("docs/AGENT_DEMO.md")
    doc_path.write_text(doc, encoding="utf-8")
    print(f"RM_AGENT_DOCS: wrote {doc_path} + {transcript_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
