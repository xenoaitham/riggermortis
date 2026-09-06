# riggermortis-mcp (Phase 3)

The MCP server that exposes the engine — and a live Blender session — to any
AI agent (Claude, Cursor, etc.). **Not implemented yet**; this directory holds
the design contract so the tool API is stable before code lands. See
`DESIGN.md` for the versioned tool schemas, the structured refusal shape, and
the transports (stdio + local socket).

Everything runs on the user's machine: no cloud, no accounts, no telemetry.
Refusal behavior is a server-side property and part of the public API.
