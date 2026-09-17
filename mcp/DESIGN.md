# riggermortis MCP server — tool contract draft (Phase 3)

Status: **design + implemented subset**. The schemas below are the
agent-facing API; they are versioned (`schema_version` in every tool) and
tested like any other surface. The server is a thin shell over
`riggermortis-core` and (for live sessions, P3-5) over a local socket to the
Blender add-on.

## Transports

- **stdio** — for local agent clients (Claude Desktop, Cursor). Default. The
  default path opens ZERO sockets (network-audit tested, now including the
  server itself: `serve_stdin_stdout` under an audit hook records no
  socket events).
- **session bridge (loopback, opt-in)** — started ONLY with both
  `--session-port N` and `--session-token HEX`; binds `127.0.0.1` and nothing
  else (hardcoded, not configurable); the Blender add-on dials IN. See the
  Session bridge section below for the protocol the add-on speaks.

## Tools

| Tool | Summary | Result shape (abridged) |
|---|---|---|
| `inspect_rig(path)` | Bone inventory + proposed role mapping + confidence per bone | `{rig, fingerprint, assignments[], core_missing[], ambiguities[]}` |
| `map_rig(path, save_preset?, overrides?)` | Apply/adjust mapping; persist per-rig preset | `{assignments[], preset_path?, notes[]}` |
| `pose_from_image(rig, image, figure_index?, mirror?)` | Detect pose, apply as FK; report quality | `{applied[], confidence, ambiguities[], warnings[]}` |
| `animate_from_video(rig, video, cleanup=true)` | Per-frame detect → smooth → retarget → cleanup v1 | `{action, frames, foot_slide_cm, coverage}` |
| `retarget_motion(rig, source, path)` | Mixamo/BVH/FBX → any mapped rig | `{action, matched_roles, warnings[]}` |
| `apply_style(scene, preset)` | Toon preset on EEVEE (anime/manga/cartoon) | `{preset, nodes_created}` |
| `render(scene, mode, out)` | turntable / viewport / panel | `{path, duration_s, engine}` |
| `compose_manga(layout, out_pdf)` | Panel layout → PDF/EPUB/PNG | `{pages, path}` |
| `policy_status()` | Reports whether the 18+ module is enabled + hard lines + the public refusal codes | `{adult_module_enabled, defaults, hard_lines[], refusal_codes[]}` |
| `policy_check(subject)` | Evaluates a hypothetical content request; refused subjects return the structured refusal below | `{allowed: true}` or the refusal shape |

## Structured refusals (part of the API)

Requests violating the content policy return HTTP-tool-error-shaped JSON,
never a traceback and never a silent no-op:

```json
{
  "error": {
    "code": "minor_content_prohibited",
    "message": "Sexual content involving minors is never permitted, regardless of fictional framing.",
    "category": "minor",
    "retryable": false
  }
}
```

Codes mirror `riggermortis.policy` exactly: `minor_content_prohibited`,
`real_person_explicit_prohibited`, `adult_module_disabled` (retryable: the
user can enable the module in preferences), `invalid_request`.

## Versioning

- Every tool declares `schema_version`; the server exposes
  `server_info()` with the contract version. Breaking changes bump the major
  version and keep the previous version available for one release cycle.

## Progress streaming (implemented, P3-4)

Long tools stream **`notifications/progress`** while they run:

```json
{"jsonrpc": "2.0", "method": "notifications/progress",
 "params": {"progressToken": "tok-1", "progress": 0.65,
            "phase": "contacts", "message": "5 contact interval(s) detected"}}
```

- The client requests tokens by passing `params._meta.progressToken` on
  `tools/call`; without a token every tool runs identically and silently.
- Notifications are emitted BEFORE the final response (stdio: written and
  flushed line-by-line); `progress` is clamped 0..1, rounded to 3 decimals;
  `phase` is a short ordered label (`load` -> `condition` -> `contacts` ->
  `lock` -> `done` for `animate_from_video`).
- Capability: `server_info().capabilities.progress_streaming = true`.
- Current streaming tool: `animate_from_video` (canonical half — load the
  job through the payload contract, stabilize -> detect -> lock, report
  frames/coverage/foot-slide). Its rig-space BAKE stays honestly
  `not_implemented` inside an otherwise successful result: it needs the
  Blender add-on path (D-009). `render`/`compose_manga` stream the same way
  once they exist.

## Example client config (Claude Desktop)

```json
{
  "mcpServers": {
    "riggermortis": {
      "command": "python3",
      "args": ["/ABSOLUTE/PATH/TO/riggermortis/mcp/riggermortis_mcp.py"]
    }
  }
}
```

Ready-made files (stdio + the opt-in session bridge) live in
[mcp/examples/](examples/); the 5-minute walkthrough is
[mcp/README.md](README.md).

## Session bridge (P3-5, implemented) — add-on ↔ server action queue

The bridge lets an agent that owns the server's stdio enqueue actions for a
LIVE, INTERACTIVE Blender (the add-on polls, executes on Blender's main
thread, posts structured results). Code lives in `mcp/session.py` (server
side, pure stdlib, import-safe without bpy) and
`addon/riggermortis_addon/session.py` (add-on side). Core stays process-free
AND socket-free (D-003).

### Topology & direction

```
agent ──stdio──> MCP server ──loopback TCP (127.0.0.1, opt-in)──> Blender add-on
   (owns JSON-RPC)      (binds 127.0.0.1 ONLY)      (add-on dials IN; user-initiated)
```

The server listens; the add-on connects out (user action inside Blender —
never an inbound connection into Blender). Multiple authenticated add-on
connections are legal; `poll` CLAIMS actions, so whichever connection polls
first gets the work (rare >1-add-on setups are still correct).

### Auth

- The server REFUSES to start the bridge unless BOTH `--session-port` and
  `--session-token` are given (no silent unauthenticated socket, ever). A
  partial config (one flag without the other) is a hard startup error.
- Token: generated by the user's shell, e.g.
  `python3 -c "import secrets; print(secrets.token_hex(16))"` (spawn lives
  outside Python per D-009). Compared with `hmac.compare_digest`.
- `hello` with a wrong/missing token → `error/auth_failed`, connection
  closed, `auth_failures` counted in `session_status`.

### Wire protocol (newline-delimited JSON, every line `{"v": 1, ...}`)

Add-on → server:

| op | fields | meaning |
|---|---|---|
| `hello` | `token`, `addon`, `version`, `blender` | first message on a connection; anything else first is `bad_request` + close |
| `poll` | `max` (1..64, default 8) | CLAIM up to `max` queued actions (queued → dispatched) |
| `result` | `action_id`, `ok`, `report` or `error` | complete a dispatched action |
| `bye` | — | clean disconnect (server acks, closes) |

Server → add-on:

| op | fields | meaning |
|---|---|---|
| `welcome` | `server_version` | hello accepted |
| `actions` | `actions[]` = `{action_id, kind, params, enqueued_at}` | poll response (possibly empty) |
| `ack` | `action_id` | result accepted |
| `error` | `code`, `message` | `auth_failed`, `bad_request`, `server_shutting_down` — then close |

Protocol violations (bad JSON, wrong `v`, unknown op, oversized line >8 MiB)
answer `error/bad_request` and close that connection; the server itself keeps
running. Non-object lines are ignored silently (defensive).

### Action lifecycle (the queue contract)

```
queued ──poll claims──> dispatched ──result──> done | failed
   │                        │
   │                     connection drops (or Blender quits)
   │                        ▼
   └── (no add-on connected:    stays dispatched, marked STALE —
        stays queued, honest    visible in action_result + ledger;
        "delivered": false)     NEVER silently re-sent
```

- `action_id`s are server-assigned, monotonic, deterministic for a given
  request order: `"a-0001"`, `"a-0002"`, …
- Every transition appends to a bounded ledger (last 256 events) surfaced by
  `session_status.recent` — the honest failure ledger. Nothing is swallowed.
- Reconnect: a new `hello` is a NEW connection; dispatched-but-unanswered
  actions from the dead connection stay `stale: true`. Idempotency is the
  caller's concern: re-enqueue if unsure (pose apply is naturally
  idempotent; that is why apply is the first executor kind).
- Blender closed: the client thread dies with the process; the server sees
  EOF/RST and marks the connection closed — same stale semantics.
- Server closed (agent closes stdio): listener + connections close, add-on
  sees the reset, backs off, keeps retrying until stopped or Blender exits.

### Agent-facing tools (schema v1, additive)

| Tool | Status | Result |
|---|---|---|
| `session_status()` | live | `{enabled, port?, listening?, addon_connected, counts {queued, dispatched, done, failed}, auth_failures, recent[]}` |
| `enqueue_action(kind, params)` | live | `{action_id, status: "queued"}` — unknown kind → `invalid_request` listing known kinds; bridge not enabled → `session_disabled` |
| `action_result(action_id)` | live | `{action_id, status, enqueued_at, dispatched_at?, completed_at?, stale?, report? \| error?}` — unknown id → `invalid_request` |

### Action kinds (add-on executor, v1)

| kind | status | params | executes |
|---|---|---|---|
| `inspect_scene` | live | `{}` | armature inventory: name, bone count, mapped-role count per object |
| `apply_pose` | live | `payload_path`, `armature_name?`, `mirror?` | the add-on's REAL payload-apply path (D-009) on the named (or active) armature; full structured report incl. per-bone self-check |
| `bake_action` | declared | `{}` | honestly answers `not_implemented` through the full queue round trip (lands with P3-7) |

Executor errors are ALWAYS structured (`{"ok": false, "error": {code,
message}}`, actionable `message` — never a traceback over the socket).

### Blender-side threading model

- ONE background thread per connection: connect (backoff 0.5s doubling, cap
  5s) → `hello` → poll/result loop. It NEVER touches `bpy`.
- A main-thread pump (registered via `bpy.app.timers`, 0.25 s) drains the
  inbound queue, executes actions through the add-on's real machinery, and
  stages results for the background thread to send. Operators remain
  undo-friendly (`push_undo`).
- Connection settings (port + token) live on `WindowManager` properties —
  session-only state, never saved to disk or into .blend files.

### What is tested (P3-5)

- Queue semantics: lifecycle, deterministic ids, stale-on-disconnect,
  unknown kind/id → structured errors, disabled-bridge honesty (pytest,
  `core/tests/test_mcp_session.py`).
- REAL loopback probe on 127.0.0.1: server + a fake add-on client executing
  an action end-to-end through a genuine socket (pytest; loopback is still
  "no external network").
- Default-path zero-sockets: the stdio server under an audit hook records
  no socket events; positive control proves the hook sees the opt-in bind.
- Golden schema: extended additively (6 → 9 tools; the v1 pin updated in the
  same commit, per the P3-3 precedent).
- Real-Blender end-to-end: `xtask/session_verify.sh` starts the server from
  shell glue, enqueues `inspect_scene` + a deliberately-failing `apply_pose`,
  and a headless Blender runs the REAL add-on client; the agent side
  collects both results (one done, one honestly failed) over stdio.
