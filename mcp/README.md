# riggermortis MCP server

The MCP server that exposes the engine — and a live Blender session — to any
AI agent (Claude Desktop, Cursor, anything speaking JSON-RPC over stdio).
Everything runs on the user's machine: no cloud, no accounts, no telemetry,
zero sockets unless YOU enable the session bridge. The tool schemas are the
agent-facing API: versioned, golden-test-pinned, and documented in
[DESIGN.md](DESIGN.md).

Status: **P3-1..P3-5 implemented and gate-tested.** Live tools:
`inspect_rig`, `policy_status`, `policy_check`, `animate_from_video`
(canonical half), `session_status`, `enqueue_action`, `action_result`.
Declared-but-pending tools answer structured `not_implemented` — never a
silent no-op.

## 5-minute connect (stdio — the default)

1. Install the engine (once):

   ```bash
   cd riggermortis
   make install PY=python3     # pip install -e "core[dev]"
   ```

2. Point your agent at the server (`mcp/examples/` has ready-made files):

   **Claude Desktop** — `claude_desktop_config.json`:

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

   **Cursor** — `.cursor/mcp.json` uses the same `mcpServers` shape.

3. Restart the agent and ask for an inspection:
   *"Use the riggermortis inspect_rig tool on out/benchmark/rigs/rigify.json."*
   The response carries the bone inventory, proposed role mapping, and
   per-bone confidence.

The stdio path opens **zero sockets** — asserted by the network-audit test
(`core/tests/test_mcp_server.py`, `core/tests/test_mcp_session.py` run the
server under a `sys.addaudithook` hook and assert no socket events).

## Live Blender session (opt-in loopback bridge, P3-5)

Lets the agent enqueue actions for an OPEN, INTERACTIVE Blender through the
add-on. The server binds `127.0.0.1` and nothing else; the add-on dials OUT
(nothing ever listens inside Blender); the wire protocol, queue semantics,
and honest failure ledger are specified in [DESIGN.md](DESIGN.md)
("Session bridge"). Full loop is gate-tested end-to-end with a real Blender
(`make session-verify`).

1. Generate a session token (in YOUR shell — the server never invents one):

   ```bash
   python3 -c "import secrets; print(secrets.token_hex(16))"
   ```

2. Start the server with BOTH flags (a partial config is refused):

   ```json
   {
     "mcpServers": {
       "riggermortis": {
         "command": "python3",
         "args": [
           "/ABSOLUTE/PATH/TO/riggermortis/mcp/riggermortis_mcp.py",
           "--session-port", "8765",
           "--session-token", "REPLACE_WITH_GENERATED_TOKEN"
         ]
       }
     }
   }
   ```

3. In Blender: install/enable the Riggermortis add-on, open the N-panel →
   **Agent session (MCP)**, enter port `8765` and the token, press
   **Connect Agent Session**. The token lives on the WindowManager —
   session-only, never saved to disk or into .blend files.

4. The agent can now drive the open Blender:

   - `session_status` → is the bridge listening, is an add-on connected,
     queue counts + the recent ledger;
   - `enqueue_action {"kind": "inspect_scene"}` → collect the armature
     inventory via `action_result`;
   - `enqueue_action {"kind": "apply_pose", "params": {"payload_path": "...",
     "armature_name": "Rig"}}` → the add-on runs its REAL payload-apply path
     (D-009) on Blender's main thread and returns the structured report,
     self-check numbers included;
   - `bake_action` is declared but honestly `not_implemented` until P3-7.

Queue semantics in one line: actions are claimed by polling, dispatched
exactly once, and never silently re-sent — if Blender quits mid-action the
result stays `dispatched` with `stale: true` in the ledger, and re-enqueueing
is the caller's call (apply is idempotent).

## Content policy is part of the API

`policy_status` reports the defaults and hard lines; refused subjects return
the exact `Refusal.to_dict()` shape with codes imported from
`riggermortis.policy` (public API — never re-typed in a frontend). Tested
byte-for-byte against a fresh default engine (`test_mcp_server.py`).
