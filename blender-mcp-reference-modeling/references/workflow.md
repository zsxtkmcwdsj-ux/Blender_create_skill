# Detailed Workflow

## 0. Intake

- Verify Blender version, MCP connection, source file, reference files, output directory, asset-library roots, and free disk space.
- Confirm whether the current scene may be cleared.
- Confirm deliverables: editable `.blend`, GLB, stills, video, local web preview, or a subset.
- Create a working copy before mutations.

## 1. Reference freeze

- Complete `assets/modeling-brief-template.md`.
- Build an evidence ledger: source, claim, confidence, and whether it identifies the target building/floor or only the broader context.
- Convert the reference into a space inventory and adjacency graph. Each space must list boundaries, openings, connections, and vertical connections.
- Read `references/spatial-grammar.md` and assign a minimum construction contract to each in-scope space type.
- List hard dimensions and estimated dimensions separately.
- Create calibrated reference planes or empties.
- Capture the untouched scene and reference overlay.
- Pause for approval.

## 2. Baseline and organization

- Set metric units and coordinate conventions.
- Create semantic collections such as `REF`, `STRUCTURE`, `ARCHITECTURE`, `VEHICLES`, `PROPS`, `RAIN`, `LIGHTS`, `CAMERAS`, and `AUDIT` only when relevant.
- Use stable semantic names and avoid renaming approved objects casually.
- Run `blender_scene_guard.py snapshot` or create an equivalent Blender text-block baseline.
- Save `stage00_baseline.blend`.

## 3. Primary blockout

- Build measured ground, walls, roads, building masses, furniture envelopes, vehicle wheels, and major clearances.
- Do not add decorative detail or furniture before the space contract passes.
- For interior architecture, block out every in-scope space as a complete envelope: floor, boundaries, ceiling or roof, and explicit openings that connect it to adjacent spaces.
- Model the adjacency graph, not just an attractive camera zone. A corridor must connect to rooms; rooms must have wall-contained doors; stairs and elevators must connect to landings.
- Classify each zone as closed, semi-open, or open. Model doors, windows, arches, stair voids, atriums, and curtain walls as explicit boundary conditions rather than implied decoration.
- Validate bounds and dimensions numerically.
- Capture a top-down graph view, a cutaway envelope view, and a human-scale interior view.
- Save and pause.

### Single-space rule

When the scope is one room or one enclosed zone, create and audit that room as a complete architectural object before expanding to adjacent spaces. Use `references/closed-space-hard-finish.md`.

- Establish a continuous shell/envelope first. Do not use furniture, floating panels, or camera framing to imply enclosure.
- Create explicit wall openings before inserting doors and windows. Verify the parent wall is absent inside the opening.
- Keep a space-to-element ledger: shell, boundary, opening, filling, finish host, and light source.
- Apply the minimum dry-room hard finish before furniture: floor finish, wall finish, ceiling finish, skirting, frame, threshold/sill, and readable light.
- Use a section or cutaway plus interior and exterior views as the minimum proof set.

## 4. Structural refinement

- Replace proxy geometry with openings, slabs, frames, supports, stairs, railings, joints, panels, body shells, glass openings, and functional connections.
- Check each door for side jambs, head, threshold, swing/leaf position, and wall continuity above the opening.
- Check each stair for landing-to-landing continuity and each elevator for shaft, landing, door, and vertical continuation.
- For continuous forms, approve the parent shell before cutting panels.
- Preserve contact, thickness, and installation logic.
- Run close-up QA for stairs, vehicles, doors, windows, HVAC, bridges, and gates.
- Save and pause.

For an enclosed room, structural refinement is not complete until the shell is continuous at corners and joints, door/window openings are real, and the head of every opening retains wall above it.

## 5. Detail refinement

- Add only approved secondary elements: handles, seals, fasteners, trim, cables, drains, shutters, lights, interior blockers, soft furnishings, or props.
- Allocate geometry by camera distance.
- Prefer instances for genuinely repeated small components.
- Validate silhouette and shading before materials.
- Save and pause.

## 6. Materials

- Index and search local asset libraries first.
- Append candidates without assigning them.
- Audit nodes and images.
- Render fixed-camera A/B previews.
- Reject candidates that only add detail while changing the material category or design palette.
- Ask before authoring a new material when the library has no accepted candidate.
- Pack accepted textures and write `MATERIAL_REPLACEMENT_REPORT`.
- Save and pause by group: ground, architecture, vehicles, props.

For a room-only deliverable, assign materials by architectural layer: floor, wall, ceiling, skirting/trim, door/window frame, glazing, and fixture. A material preview that cannot distinguish these layers fails the hard-finish gate.

## 7. Lighting and environment

- Use lights with visible or defensible sources.
- Balance environment fill, interiors, signs, streetlights, vehicle lights, and depth lights.
- For wet scenes, separate wet substrate, thin film, irregular puddles, drains, edge feathering, ripples, and rain.
- Avoid a single mirror plane, uniform blue wash, or identical procedural noise on all materials.
- Save dry/wet and old/new A/B views.
- Save and pause.

## 8. Camera and animation

- Duplicate the approved static file into a cinematic file.
- Use editable camera rigs, targets, and constrained keyframes.
- Check collision clearance and framing at key frames.
- Render low-resolution keyframe previews before the final sequence.
- Render PNG or EXR sequences, then encode video.

## 9. Delivery

- Clean temporary audit objects and rejected materials.
- Re-run geometry, material, texture, hierarchy, frame-range, and baseline verification.
- Pack the `.blend` when requested.
- Export only requested formats.
- Re-import GLB in a temporary scene and generate a report.
- Record limitations and exact output paths.

## Failure recovery

- On Python error, report the exact error and verify whether partial data was created before retrying.
- On MCP timeout, verify Blender process health, current file path, scene counts, and output file existence.
- On Blender crash, reopen the latest checkpoint and compare against the last accepted manifest.
- Never resume from an unverified autosave when an accepted checkpoint exists.
