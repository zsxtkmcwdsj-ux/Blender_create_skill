# Spatial Grammar

Use this contract for every architectural interior. A room is not a collection of furniture; it is a bounded volume with explicit openings and connections.

## Evidence model

For each fact, record one of: `confirmed` (directly shown or dimensioned), `inferred` (needed architectural assumption), or `unknown` (do not silently invent a specific claim). Keep building identity, floor identity, and visual relevance as separate verdicts.

## Space record

Every space must list its type, evidence status, boundary mode, floor, walls, ceiling, openings, connections, vertical geometry, and contents. The adjacency graph must say which opening connects which two spaces; prose alone is insufficient.

## Minimum construction grammar

### Room

- floor slab or finished floor;
- four side boundaries, or an explicit open edge;
- ceiling slab or exposed structure;
- a real door opening to circulation, including side jambs and head above the door;
- windows or other exterior openings when the plan/elevation implies an exterior edge;
- furniture only after the envelope passes.

### Corridor

- continuous floor and ceiling;
- room-front boundaries on the sides;
- a door opening for every connected room in scope;
- readable width, clearance, end conditions, and connections to stairs, elevators, lobbies, or exits.

### Stairwell

- enclosed shaft or stair room with wall thickness;
- lower landing, upper landing, and at least one continuous flight;
- individual treads and risers or a clearly modeled stair slab;
- handrail/stringer when visible;
- an opening from the corridor and a vertical continuation, not a solid placeholder block.

### Elevator

- shaft/core boundaries;
- landing in front of the lift;
- door opening with head and jambs;
- cabin or shaft depth visible in cutaway;
- overhead/vertical continuation represented by a shaft volume or explicit scope note.

## Build order

1. Parse the plan into spaces, boundaries, openings, and an adjacency graph.
2. Build all floors, walls, ceilings, and vertical cores.
3. Cut and frame doors, windows, stairs, elevators, and other connections.
4. Run cutaway and top-down checks; repair missing or floating boundaries.
5. Add furniture and visual detail inside accepted spaces.
6. Apply materials, lighting, and cameras.

## Acceptance checks

- Furniture is never proof that a room exists.
- Every closed room must have floor, side boundaries, ceiling, and framed openings.
- Every door must sit inside a wall with visible wall above it.
- Every vertical core must show a real vertical mechanism, not a black box.
- At least one view must show the human-scale interior, one the adjacency graph, and one the stair/elevator connection when in scope.
- The audit must list missing evidence and inferred dimensions separately.

## Single-room hard-finish gate

For a single enclosed room, use `references/closed-space-hard-finish.md` in addition to this grammar.

- Build one continuous envelope or one semantically unified shell before adding finish pieces.
- Keep wall thickness and make the floor-to-wall and wall-to-ceiling boundaries physically continuous.
- Treat every door/window as `wall -> opening -> filling -> adjacent space`, not as a panel placed on a wall.
- Test openings from both sides and in a section view; no parent wall face may remain behind a filling.
- Add floor, wall, ceiling, skirting, threshold/sill, frame, and source-driven light before furniture.
- Mark conditional details such as sockets, HVAC, sprinklers, drains, acoustic panels, and waterproofing as required, conditional, or out of scope.
- Do not accept a rendered room until the hard-finish layer is visually readable and the space audit reports no missing required envelope element.
