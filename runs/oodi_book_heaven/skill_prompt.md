# Blender Skill Handoff: Helsinki Central Library Oodi

Use `blender-mcp-reference-modeling` to build a complete, editable concept interior scene of the real **Helsinki Central Library Oodi**, by ALA Architects.

## Scope and truth status

- Mode: `concept_spatial_modeling`.
- Target: top-floor `Book Heaven` reading environment with the `Citizens' Balcony`.
- Verification: building identity high; selected floor and camera area medium; visual relevance high.
- This is a spatial concept, not a measured reconstruction. Inferred dimensions and furniture placement must stay visibly subordinate to the documented architectural relationships.

## Frozen spatial brief

- Open reading floor: 28 m wide x 18 m deep concept area, 5.2 m clear height.
- Rear anchor: a curved laminated timber volume / book-service spine.
- Public edge: continuous glazed facade and balcony overlooking the city.
- Vertical landmark: simplified double-helix stair next to the timber spine.
- Central field: low book stacks, reading tables, lounge islands and trees.
- Side zones: a small cafe nook and a children's reading oasis.
- Circulation: maintain a clear loop from stair to balcony and back through the central reading field.

## Visual language

Warm Finnish wood, white acoustic undulating ceiling, clear glass, light concrete, muted blue/green upholstery and restrained brushed metal. Daylight dominates; warm pendants mark reading islands. The hero camera must show the curved timber volume, stair, book floor, ceiling and balcony edge together.

## Staged execution

1. Intake and reference freeze: store the research sources and truth limits in scene metadata.
2. Coordinate setup: metric units, semantic collections, stable names and a baseline checkpoint.
3. Primary blockout: floor, balcony, glazed wall, timber volume, stair envelope and ceiling envelope.
4. Structural refinement: curved timber ribs, double-helix stair, balcony rails, ceiling waves and skylights.
5. Detail refinement: book stacks, desks, reading oases, cafe counter, plants and signage.
6. Materials: use local library materials if available; otherwise use simple authored Principled materials and record that fallback.
7. Lighting and camera: diffuse daylight plus warm reading pools, one hero camera and one overview camera.
8. Validation and delivery: save `.blend`, export `.glb`, render a PNG preview, re-import and validate GLB.

## Deliverables

Write all final files to `outputs/oodi_book_heaven/`:

- `oodi_book_heaven.blend`
- `oodi_book_heaven.glb`
- `oodi_book_heaven_preview.png`
- `scene_audit.json`
- `glb_validation.json`

Research sources: ALA Architects, Oodi official floor information, European Commission architecture catalogue, and ArchDaily plan/material reference.
