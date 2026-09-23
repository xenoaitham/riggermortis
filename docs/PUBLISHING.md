# Publishing runbook (the human-click parts)

Everything automatable is done. What remains needs YOUR accounts.

## GitHub — DONE 2026-09-15

- Repo: **https://github.com/xenoaitham/riggermortis** (public, MIT).
- Branch `main` (default), CI workflow ran for the first time on the first
  push (tests matrix 3.11/3.13 + blender-gate + media-guard).
- If the org/repo should live under a different account: Settings →
  Transfer ownership, then update `Homepage`/`Issues` in `core/pyproject.toml`
  and the URLs in README.md.

## PyPI — one command, needs your account

1. Create a PyPI account (https://pypi.org/account/register/) and enable 2FA.
2. Generate an API token (Account settings → API tokens, scope: project).
3. Then:
   ```
   make dist PY=python3                 # builds dist/* + twine check (DONE, PASSED)
   python3 -m twine upload dist/riggermortis_core-0.0.1.*
   ```
   (twine will prompt for the token: username `__token__`, password the token.)
4. Post-upload: add the project description on pypi.org, verify
   `pip install riggermortis-core` works in a fresh venv, then
   `pip install 'riggermortis-core[inference]'` + `rigpose models download all`
   end-to-end.

Notes:
- Package name on PyPI is `riggermortis-core` (this distribution is the
  core + `rigpose` CLI). The bare `riggermortis` PyPI name was confirmed free
  in D-001 and stays reserved for a possible future unified distribution —
  do NOT squat it casually; consider registering an empty placeholder only
  if you actually plan to use it.
- Version is 0.0.1 (Pre-Alpha classifier). Bump per release; PyPI names are
  permanent — the first upload claims the name.

## Blender Extensions — needs your blender.org account

1. Account at https://extensions.blender.org (confirmed free in D-001).
2. The add-on manifest (`addon/riggermortis_addon/blender_manifest.toml`)
   targets Blender 4.2+; the repo gate runs 4.0.2 — retest the manifest
   against a 4.2+ build before uploading. RETESTED (post-S25 triage,
   2026-09-23): builds clean on the dev box's real 5.1.0 —
   `blender --command extension build --source-dir addon/riggermortis_addon
   --output-dir <dir>` → `riggermortis-0.0.1.zip` (~80 KB). Rebuild right
   before uploading so the zip carries the current tree.
3. Upload the built extension zip, fill the listing (description from
   README, MIT license, tag: Rigging), submit for review.

## MCP registry listing — needs your registry account

Everything preparable is prepared; the submission itself is account-bound.

- **Manifest:** `mcp/manifest.json` carries the listing metadata (name,
  version, local-only guarantee, transport, capabilities) and the honest
  tool table — pinned by
  `core/tests/test_mcp_server.py::test_registry_manifest_matches_the_server_exactly`
  to match the server's golden schema exactly (9 tools: 8 live,
  `pose_from_image` declared; schema v1). Bump `manifest.version` and
  `SERVER_VERSION` in the same commit, always.
- **Capability claims a listing may copy** (each cites its proof):
  - stdio JSON-RPC 2.0, zero sockets by default — network-audit test with a
    positive control (`test_mcp_session.py`);
  - opt-in session bridge on 127.0.0.1 ONLY, token auth, stale-on-disconnect
    queue semantics — real-socket tests + `make session-verify`;
  - end-to-end agent loop (inspect → pose → animate → bake → turntable) —
    `docs/AGENT_DEMO.md` + the committed transcript + `make agent-demo`;
  - structured policy refusals mirroring `riggermortis.policy` —
    `test_mcp_server.py` byte-for-byte shape tests.
- **Submission runbook:** create the registry account, then submit with the
  manifest fields above (the official `server.json` mapping is filled at
  submission time against the registry's then-current schema — do not
  pre-bake spec fields here that can drift). Listing description source of
  record: README + `mcp/README.md`. After approval: verify `initialize`
  answers and `tools/list` returns 9 entries from a fresh client.
