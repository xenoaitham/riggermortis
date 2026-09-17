# Agent demo — one MCP conversation, zero human Blender interaction

Phase-3 gate asset (P3-7 E2E agent demo). A scripted agent owns the riggermortis MCP
server's stdio and drives a LIVE Blender through the whole loop:

```
agent --stdio--> MCP server --loopback 127.0.0.1--> Blender add-on (headless)
                                     (session bridge, token auth)
```

![agent-driven turntable](agent_turntable.gif)

## The conversation

| the agent asks | through | answer (from the run) |
|---|---|---|
| what is this rig? | `inspect_rig` | 21 roles mapped, min confidence 0.75 |
| what is live right now? | `enqueue_action` -> `inspect_scene` | armature inventoried inside Blender |
| pose it from the photo | `enqueue_action` -> `apply_pose` | 16 bones applied, self-check worst 0.0000 deg |
| animate from the video job | `animate_from_video` | 70 canonical frames, foot slide 0.8153 -> 0.0 u; bake routed to the session action |
| bake it on the rig | `enqueue_action` -> `bake_action` | 1120 keys, 59 locked frames, re-eval 0.0210 deg (lock dev 12.6053 deg, 5 contact intervals) |
| show me | `enqueue_action` -> `render_turntable` | 35 orbit frames rendered, playing the baked action |

The verbatim exchange (requests `>>>`, responses `<<<`, progress
notifications included) is committed next to this file:
[agent_demo_transcript.txt](agent_demo_transcript.txt).

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
