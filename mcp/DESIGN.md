# riggermortis MCP server — tool contract draft (Phase 3)

Status: **design draft**. The schemas below are the agent-facing API; they are
versioned (`schema_version` in every tool) and tested like any other surface.
The server is a thin shell over `riggermortis-core` and (for live sessions)
over a local socket to the Blender add-on.

## Transports

- **stdio** — for local agent clients (Claude Desktop, Cursor). Default.
- **local socket** — `127.0.0.1` only, for the add-on bridge and multi-tool
  setups. Never binds external interfaces; no auth over loopback because no
  network leaves the machine (CI network-audit test covers this).

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
      "command": "rigpose-mcp",
      "args": ["--transport", "stdio"]
    }
  }
}
```
