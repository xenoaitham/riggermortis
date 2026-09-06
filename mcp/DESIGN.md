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
| `policy_status()` | Reports whether the 18+ module is enabled + hard lines | `{adult_module_enabled, defaults, hard_lines[]}` |

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

## Progress streaming

Long tools (`animate_from_video`, `render`, `compose_manga`) stream progress
notifications (`phase`, `0..1`, message) so agents can report status instead
of hanging on a silent call.

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
