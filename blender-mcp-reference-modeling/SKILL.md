---
name: blender-mcp-reference-modeling
description: Build, refine, validate, and deliver Blender scenes through Blender MCP from approved reference images, orthographic drawings, dimension sheets, or existing .blend checkpoints. Use for visible staged modeling, strict reference matching, hard-surface vehicles or architecture, material-library-first look development, rain/night scenes, camera animation, GLB delivery, or local web previews where geometry, proportions, materials, checkpoints, and user approvals must be preserved.
---

# Blender MCP Reference Modeling

Use Blender's native Python API through MCP to build or refine scenes visibly, in small reviewable stages. Treat approved dimensions and reference views as constraints, not inspiration.

## Start safely

1. Verify Blender MCP connectivity with a read-only scene query.
2. Confirm the following before any destructive or creative action:
   - approved reference images and their priority;
   - output directory and required deliverables;
   - whether clearing the current scene is authorized;
   - checkpoint cadence and which stages require explicit approval;
   - configured local material-library paths;
   - whether custom materials may be created if no library material passes A/B review.
3. Save the current file to a new working filename before editing. Never overwrite an unrelated or user-owned checkpoint.
4. Create an immutable baseline manifest before changing geometry, transforms, lights, rain, or animation. Use `scripts/blender_scene_guard.py snapshot` when practical.

Read [references/reference-rules.md](references/reference-rules.md) whenever reference images, dimensions, or multiple views govern the result.

## Execute the staged workflow

Use these stages unless the user supplies a stricter plan:

1. **Intake and reference freeze** — inventory files, extract hard dimensions, identify conflicts, and obtain approval for the frozen brief.
2. **Scene and coordinate setup** — establish units, axes, origin, collections, naming, reference planes, cameras, and baseline hashes.
3. **Primary blockout** — create only the measured room/site, major masses, roads, furniture, vehicles, or structural envelopes.
4. **Structural refinement** — replace placeholders with usable construction: openings, frames, supports, stairs, panels, joints, hardware, and continuous surfaces.
5. **Detail refinement** — add only reference-supported secondary details and close-up geometry.
6. **Materials** — inspect the user's local asset libraries first, run fixed-camera A/B checks, and retain a candidate only when it is visibly and physically better.
7. **Lighting and environmental effects** — preserve the approved palette and create source-driven lighting, rain, wetness, reflections, fog, or atmosphere only when requested.
8. **Camera and animation** — animate a separate cinematic working file unless the user explicitly wants animation in the static deliverable.
9. **Validation and delivery** — validate dimensions, hierarchy, normals, materials, missing files, animation, exports, and re-imported deliverables.

Pause at every stage the user marked for confirmation. Do not continue because the previous step merely completed without errors.

Read [references/workflow.md](references/workflow.md) for the detailed phase gates and recovery procedure.

## Model by structure, not by assembly illusion

- Build major hard-surface forms as coherent parent surfaces or structurally connected assemblies.
- Derive doors, hoods, glass, panels, trim, openings, and seals from approved boundaries. Do not cover gaps with floating plates.
- For vehicles, begin with calibrated side/top/front/rear views, wheel centers, wheelbase, overhangs, clearance, and overall dimensions. Create a continuous body shell before separating panels.
- For architecture, avoid cloning one complete facade, window, stair, or HVAC module across every building. Repetition must follow the approved elevations and include supported variation.
- Construct stairs with steps, stringers, platforms, beams, braces, posts, rails, kick plates, wall connections, and contact shadows when visible.
- Keep close-up assets detailed enough for their nearest approved camera; do not raise subdivision without improving silhouette or curvature.
- Never download or generate geometry with online model services, one-click AI 3D tools, or uncommon third-party plugins unless the user explicitly authorizes that exact source.

## Preserve shading integrity

- Use `bpy.ops.object.shade_smooth_by_angle` or the current Blender equivalent for angle-controlled smoothing.
- Do not call ordinary `shade_smooth`.
- Preserve sharp edges, custom normals, bevel intent, and existing smoothing state unless the user authorizes a change.
- Validate non-manifold edges, reversed normals, duplicate faces, zero-area faces, negative scale, intersections, floating parts, and broken modifiers.

Read [references/quality-gates.md](references/quality-gates.md) before accepting refined geometry or close-up assets.

## Apply materials with library-first approval

1. Inspect configured local asset libraries before creating a material.
2. Audit each candidate for valid output nodes, required PBR channels, missing images, incompatible nodes, OSL dependencies, texture scale, repetition, and render cost.
3. Compare the original and candidate from the same camera, frame, exposure, lights, engine, resolution, and sample count.
4. Preserve approved colors, markings, labels, wetness layers, object assignments, and design relationships.
5. Accept a candidate only when it is clearly more realistic. Reject detail that changes the material category, such as paving normals on asphalt.
6. Append accepted data locally, rename it with a `LIB_` prefix, record its source, and pack its images.
7. If no asset passes, stop and ask whether custom material authoring is allowed. Do not silently create one.

Read [references/materials-lighting.md](references/materials-lighting.md) for A/B criteria, glass, vehicle paint, wet surfaces, and lighting rules. Use `scripts/material_library_index.py` to inventory portable `.blend` material libraries.

## Work visibly through MCP

- Send concise user updates before tool calls and at least once per minute during long work.
- Execute small, idempotent Python batches. Save after each successful batch.
- Keep semantic collections and object names. Store audit reports in Blender text blocks and external JSON when useful.
- Capture viewport screenshots or fixed-camera previews after each gate.
- If MCP times out during a render, first check whether Blender is still alive and whether the output file was written. Do not repeat a completed render blindly.
- On crash, reopen the latest verified checkpoint, audit it, and resume from the first incomplete stage.

Read [references/mcp-execution.md](references/mcp-execution.md) for connection checks, safe batching, and recovery.

## Validate and deliver

- Keep editable `.blend` checkpoints for every approved phase.
- Pack or localize external resources only after their candidates are accepted.
- Export GLB from a static delivery file unless animation is explicitly required.
- Re-import GLB in a temporary background Blender process and verify bounds, hierarchy, materials, images, normals, and animation.
- State clearly that Cycles lights, compositor effects, volumes, particles, and some procedural materials cannot be reproduced exactly in GLB.
- Render image sequences before video encoding so interrupted renders can resume.
- Do not render a final video, export GLB, publish a web preview, or overwrite a delivery unless the user requested that output.

Read [references/delivery.md](references/delivery.md) for GLB, cinematic, and web-preview procedures. Run `scripts/validate_glb.py` in a separate background Blender process for export checks.

## Reusable project artifacts

Copy and fill only the templates needed for the task:

- `assets/modeling-brief-template.md` — frozen reference hierarchy, dimensions, scope, and deliverables.
- `assets/stage-acceptance-template.md` — stage decisions, evidence, and approval log.
- `assets/material-replacement-report-template.md` — material A/B decisions and source tracking.

For installation and example prompts on another computer, read [references/usage-guide-zh.md](references/usage-guide-zh.md).
