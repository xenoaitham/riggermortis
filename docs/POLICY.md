# Content Policy

This is the project's spine. It is enforced **in the engine core, in code**
(`riggermortis/policy.py`), which means neither the Blender add-on nor the MCP
server can bypass it — they are thin shells over the core.

## Defaults

- The default build is **SFW**. Fresh installs have the adult module disabled,
  and an automated test proves it stays that way.
- The engine is a tool. It ships no sexual content, downloads none, and
  embeds none. Public-facing materials (README, docs, demos, screenshots,
  issue templates) contain no adult content.

## Opt-in 18+ module

Users may enable an adult module in preferences **with explicit confirmation**
(two toggles, clearly labeled). When enabled, it permits explicit content of
**fictional adult characters only**, processed and rendered 100% locally.

The module is documented soberly, exactly as this page documents it. It adds
capability; it does not change the lines below.

## Absolute lines (never toggleable, enforced in core where technically possible)

1. **No sexual content involving minors** — real or fictional, regardless of
   "fictional" framing. This is a hard stop, not a preference. Requests return
   a structured refusal (`minor_content_prohibited`).
2. **No explicit content of real, identifiable people.** There is no
   photo-to-explicit pipeline in this engine, by design, at the architecture
   level: image-driven posing applies to fictional rigs only.
3. **Nothing illegal in the user's jurisdiction.**

## Where the lines live in code

- `riggermortis/policy.py` — `PolicyEngine`, `Refusal`, stable refusal codes.
- Refusal codes are part of the public API: the add-on reports them verbatim
  (`refused [<code>] …`), the MCP server returns them as structured tool
  errors, and tests pin them.
- `PolicyEngine` cannot be constructed with the adult module enabled; the only
  path is `enable_adult_module(confirm=True)` on a default instance, which is
  exactly what the add-on preferences flow does.
- The add-on binding (`addon/riggermortis_addon/policy.py`) owns the add-on's
  single engine, always built through the default (SFW) path. The two
  preference toggles ("Enable 18+ module" + "I understand the policy") are
  the only user-facing control; syncing derives the engine state through the
  documented calls only, and enabling requires BOTH toggles.
- The MCP server has **no enable path**: it builds a fresh default engine per
  call and its tool table carries no enable/confirmation tool. Agents cannot
  turn the module on anywhere — only the human, locally, in Blender
  preferences.

## Enforcement (P6-4/P6-5, test-pinned in both frontends)

- Core: default-SFW status, the construction guard, strict `confirm is True`
  semantics, and every refusal's code/retryability (core test suite).
- Add-on: the bpy-free binding is unit-tested headlessly (fresh-install OFF,
  both-toggles rule, verbatim codes in the report line); the REAL preferences
  flow — real `AddonPreferences` defaults, real toggle writes, the addon
  enabled the way the user's checkbox does — runs in the Blender gate
  (`xtask/blender_verify.sh`, `RM_POLICY` lines, grep-tested).
- MCP: `policy_status` answers OFF on a fresh server, no tool enables the
  module, repeated calls never drift the server enabled, and the gated
  subject refuses with the exact code (golden-schema-pinned tests).
- The network-audit test extends the zero-outbound sweep over the binding
  (both toggle states, a full check sweep) — the module adds no default-use
  network surface.

## Network promise

Default use makes **zero outbound connections**. Model weights are downloaded
once, checksum-pinned, only when the user asks for them, directly from their
published sources. A CI network-audit test enforces this. "Your models never
leave your machine" is a headline; this is what keeps it true.
