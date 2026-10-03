# Blender Skill Handoff: Suzhou Museum New Building

Use `blender-mcp-reference-modeling` to build a complete editable concept interior of the real **Suzhou Museum New Building**, designed by I.M. Pei with Pei Partnership Architects.

## Scope and truth status

- Mode: `concept_spatial_modeling`.
- Target: one enclosed exhibition gallery, its covered cloister, and a semi-open water courtyard.
- Verification: building identity high; exact selected room medium; visual relevance high.
- This is a spatial concept synthesis, not a measured reconstruction.

## Mandatory spatial envelope gate

Start with a real volumetric composition, not a display platform. The main gallery must have a continuous floor, four-sided wall enclosure, wall thickness, a pitched geometric ceiling, a door opening and a geometric window opening. The cloister must have a roof, columns/walls and a floor. The courtyard must be open to sky but bounded by the surrounding building edges, low walls, water and planting. Model the stair as a real floor-to-floor connection with landings and an opening in the slab.

Classify zones as `closed`, `semi-open` or `open`. Build the shell and openings before furniture or decorative props. Provide a hero interior camera and a cutaway/section overview camera that proves the shell and adjacency.

## Frozen spatial brief

- Closed white gallery: 10 m x 7 m, concept height 4.2 m.
- Thick doorway: gallery to covered cloister.
- Geometric side window: high angled / hexagonal opening toward the courtyard.
- Covered cloister: 3 m deep, repeated dark columns, white wall returns and roof edge.
- Semi-open water court: 12 m x 8 m, shallow reflective pool, bridge, rocks, bamboo and white perimeter walls.
- Central hall: higher geometric roof with triangular skylights.
- Two-story stair: black steel, attached to actual floor landings at the hall edge.

## Visual language

White plaster walls, dark gray roof/stone, dark tile floor, light granite, black steel, clear glass, water and garden stone. Use soft skylight and angled-window daylight with restrained warm gallery spots. Compose framed views and shifting perspective, not a generic open room.

## Staged execution

1. Intake and truth freeze: record sources and mark inferred dimensions.
2. Envelope blockout: floor slabs, full gallery walls, ceiling/roof, cloister, courtyard boundary and stair void.
3. Opening refinement: real doorway, window reveal, glazed opening, roof skylights, thresholds and wall thickness.
4. Structure/detail: columns, stair landings, bridge, parapets, garden rocks, bamboo and display plinths.
5. Materials and lighting: local library first; simple authored materials only if needed and record the fallback.
6. Cameras: hero interior plus cutaway/section overview.
7. Validation: bounds, openings, object hierarchy, GLB re-import and preview inspection.

## Deliverables

Write all final files to `outputs/suzhou_museum_new/`:

- `suzhou_museum_new.blend`
- `suzhou_museum_new.glb`
- `suzhou_museum_new_preview.png`
- `suzhou_museum_new_cutaway.png`
- `scene_audit.json`
- `glb_validation.json`
