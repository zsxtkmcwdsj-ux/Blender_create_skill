# Closed Space and Hard-Finish Contract

Use this contract when the scope is one room, one interior zone, or one enclosed architectural space.

## 1. Space is a bounded volume

The model must begin as a continuous room envelope, not as a camera-facing collection of fragments.

Required envelope elements:

- floor slab or finished floor;
- continuous left, right, front, and back boundaries, unless the brief explicitly marks an open edge;
- ceiling slab, roof, or exposed structural ceiling;
- wall thickness at every boundary;
- a named space volume and a named shell/envelope object.

The envelope must be watertight enough that a camera or ray cannot see an accidental gap at a corner, wall-to-floor joint, wall-to-ceiling joint, or wall-to-wall joint.

## 2. Openings are relationships, not stickers

Every door or window consists of:

1. a real void in the parent wall;
2. retained wall construction around the void;
3. jambs and head/lintel;
4. threshold or sill;
5. door leaf or glazing;
6. a connection to the adjacent space or exterior edge.

Never place a door or window panel over an intact wall face. Before export, test the opening from both sides and verify that no parent wall face remains behind the opening.

## 3. Hard finish is a layered construction

Required for a normal dry room:

- floor finish with a believable material category;
- wall finish, such as paint, plaster, tile, or exposed concrete;
- ceiling finish or exposed slab/structure;
- skirting/baseboard at wall-floor junctions, interrupted at door openings;
- door/window frame finish;
- visible threshold or sill where the opening requires one;
- at least one plausible room light source and readable illumination.

Conditional elements:

- corner guards, reveals, shadow gaps, cornices, or wall panels;
- switches, sockets, detectors, sprinklers, HVAC grilles, and access panels;
- waterproofing, floor drain, wall tile, and ceiling service access in wet rooms;
- curtain track, blinds, acoustic panels, or fire/smoke seals when supported by the brief.

Do not add conditional elements just to make an empty room look busy. Add them when the building type, reference, code context, or camera requires them.

## 4. Space-to-element ledger

Record these relationships in the brief and audit:

- `space -> boundary element`;
- `wall -> opening`;
- `opening -> door or window filling`;
- `door -> adjacent space`;
- `window -> exterior or secondary space`;
- `finish -> host boundary`;
- `light -> visible or defensible source`.

Each relationship is `confirmed`, `inferred`, or `unknown`. Unknown dimensions must not be presented as measured facts.

## 5. Acceptance gate

Accept the room only when all of the following are true:

- the envelope reads as one enclosed space from exterior, interior, and section views;
- wall corners, wall-floor, and wall-ceiling joints have no unintended gaps;
- every door/window is an actual opening with wall above and beside it;
- no wall face is hidden behind a door/window filling;
- floor, wall, ceiling, skirting, frame, and light are distinguishable in the material/rendered view;
- the audit reports missing required elements and inferred dimensions separately;
- furniture is still optional and cannot be used as proof that the room exists.

