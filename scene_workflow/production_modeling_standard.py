from __future__ import annotations

EXTERIOR_STANDARD = [
    "focus on the requested building only; do not fill the scene with unrelated trees or decoration",
    "lock the main silhouette, proportions and tier relationships before adding ornament",
    "model real circulation parts: stairs need treads, risers, landings, side rails and clear railing openings",
    "model guardrails as separate posts, panels, caps and directional breaks rather than continuous rings through entrances",
    "add facade depth: columns, doors, lattice panels, plaques, brackets, eaves and visible joints",
    "add roof depth: tiered masses, ribs, tile courses, eave trim, underside structure and finial details",
    "use material variation: color, roughness, procedural noise and bump so the browser GLB is not a white clay model",
    "render hero and close-up checks for overall shape, roof/eave detail, facade detail and stair/terrace detail",
    "validate the exported GLB before publishing it to the model showcase",
]

INTERIOR_STANDARD = [
    "build a complete enclosed space first: walls, floor, ceiling, doors, windows and openings",
    "add hard finishes before furniture: baseboards, trims, seams, material changes and lighting anchors",
    "model furniture as structured objects with thickness, joints and believable scale",
    "use material variation and lighting checks so the scene does not read as a white box",
    "render whole-room and detail checks before publishing the GLB",
]

def modeling_standard(module: str) -> list[str]:
    return EXTERIOR_STANDARD if module == "exterior_architecture" else INTERIOR_STANDARD
