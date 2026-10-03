# Materials, Wetness, and Lighting

## Library-first material selection

1. Build or refresh a material index from configured asset libraries.
2. Select candidates by material category, color range, physical response, texture resolution, and scale.
3. Append candidates locally. Do not link final delivery materials to a machine-specific library path.
4. Reject missing images, pink materials, disconnected outputs, OSL/script dependencies, incompatible nodes, or excessive render cost.
5. Compare at identical camera, frame, exposure, lights, engine, resolution, and samples.
6. Keep the original when improvement is ambiguous.
7. Ask the user before custom authoring when no candidate passes.

## Vehicle paint

- Preserve the approved color.
- Separate base coat, metallic flakes, and clear coat.
- Keep flakes below visible glitter size at the nearest camera.
- Use continuous reflections to evaluate panel curvature.
- Reject procedural sparkle that reads as render noise.

## Glass

- Preserve real openings, seals, thickness, and interior depth.
- Balance reflection, refraction/transmission, IOR, roughness, tint, and absorption.
- Verify the interior remains appropriately readable.
- Apply rain traces only to selected close windows, not every pane with the same pattern.

## Wet ground

- Separate substrate, damp variation, thin water film, irregular puddles, feathered wet edges, ripples, and drainage zones.
- Place deeper water near curbs, drains, low points, and wheel tracks.
- Use irregular boundaries and interrupted reflections.
- Reject complete mirror planes, regular ellipses, hard-edged puddles, or paving normals on asphalt.

## Lighting

- Use explicit sources: sky fill, interiors, signs, streetlights, vehicle lights, and distant depth lights.
- Preserve detail in dark areas and text in bright signs.
- Avoid one-color environmental washes.
- Let metal, glass, rubber, paint, concrete, and wet surfaces respond differently.
- Use volume only to support depth or beams; do not hide weak modeling with fog.
