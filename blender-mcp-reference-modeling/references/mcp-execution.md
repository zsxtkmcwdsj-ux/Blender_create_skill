# Blender MCP Execution

## Connection

1. Ask the user to start Blender and the Blender MCP server/add-on.
2. Query scene information read-only.
3. If unavailable, inspect the exposed MCP tool list before suggesting installation or configuration.
4. Do not assume a port, add-on name, or Blender version without verification.

## Safe batch pattern

- Keep each Python call focused on one bounded change.
- Validate required objects and materials before mutating.
- Wrap temporary assignments in `try/finally` and restore the original state.
- Save after a successful batch, not before error inspection.
- Make operations idempotent: look up existing data by stable name before creating it.
- Record source paths as custom properties, but do not hardcode credentials or private endpoints.

## Visible progress

- Keep the intended camera or viewport visible.
- Create objects in small groups so the user sees them appear.
- Capture screenshots after structural milestones.
- Stop at approval gates.

## Long renders

- Use low samples for candidate screening and the approved sample count for final A/B.
- After first-kernel compilation, later renders may be much faster; record actual timings.
- If the MCP response times out, check Blender connectivity, render-result existence, output-file size, and completion properties before re-rendering.

## Recovery

- Inspect partial imports after append errors; Blender may have created datablocks before the Python exception.
- Remove only known temporary or rejected datablocks. Do not run broad orphan purges in a user scene without approval.
- Reopen the last accepted checkpoint after a crash and verify scene counts, hashes, frame range, camera, and materials before continuing.
