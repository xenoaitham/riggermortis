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
- Refusal codes are part of the public API: the add-on reports them verbatim,
  the MCP server returns them as structured tool errors, and tests pin them.
- `PolicyEngine` cannot be constructed with the adult module enabled; the only
  path is `enable_adult_module(confirm=True)` on a default instance, which is
  exactly what the add-on preferences flow does.

## Network promise

Default use makes **zero outbound connections**. Model weights are downloaded
once, checksum-pinned, only when the user asks for them, directly from their
published sources. A CI network-audit test enforces this. "Your models never
leave your machine" is a headline; this is what keeps it true.
