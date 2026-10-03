from __future__ import annotations

from typing import Any


EXTERIOR_DETAIL_TARGETS = [
    "overall silhouette and tier proportions",
    "base or plinth connection to the ground",
    "entrances, doors, windows and facade rhythm",
    "stairs with real treads, risers, landings and rail openings",
    "guardrails split into posts, panels, caps and breaks at entrances",
    "roof massing, eaves, ribs, tile courses, underside structure and finial details",
    "material separation for stone, timber, roof tile, metal trim and paving",
]

INTERIOR_DETAIL_TARGETS = [
    "complete room envelope: floor, walls, ceiling and real openings",
    "doors and windows as holes with frames, thresholds and sills",
    "hard finishes: floor finish, wall finish, ceiling finish, skirting and trims",
    "lighting anchors and material variation before loose decoration",
    "furniture with believable thickness, joints, scale and circulation clearance",
]

MATERIAL_HINTS = {
    "stone": ("stone", "marble", "granite", "\u77f3", "\u6c49\u767d\u7389", "\u5927\u7406\u77f3"),
    "timber": ("wood", "timber", "lacquer", "\u6728", "\u67f1", "\u7ea2\u67f1", "\u6f06"),
    "glass": ("glass", "glazing", "\u73bb\u7483", "\u7a97"),
    "metal": ("metal", "gold", "bronze", "\u91d1", "\u94dc", "\u91d1\u5c5e"),
    "roof_tile": ("tile", "glazed", "roof", "\u74e6", "\u7409\u7483", "\u5c4b\u9876"),
    "fabric": ("fabric", "curtain", "carpet", "\u5e03", "\u7a97\u5e18", "\u5730\u6bef"),
}

FEATURE_RULES = [
    {
        "name": "compound_roof_and_tiles",
        "terms": ("roof", "tile", "glazed", "\u5c4b\u9876", "\u7409\u7483\u74e6", "\u91cd\u6a90", "\u6b47\u5c71", "\u89d2\u697c"),
        "rules": [
            "roof cannot be a single flat slab; use separate roof mass, eave underside, raised ridges and repeated tile plates or tile ribs",
            "model main ridge, vertical ridges and diagonal hip ridges when the reference implies compound or hip roofs",
            "stacked roof tiers must have visible support bodies, columns or bracket layers between tiers; no upper roof may float above empty air",
            "add finial, ridge caps, eave trim and upturned corner emphasis when visible",
        ],
        "failure_check": "roof close-up fails if the roof reads as one smooth board, lacks tile/ridge hierarchy, or any tier floats without support",
    },
    {
        "name": "dougong_brackets",
        "terms": ("dougong", "bracket", "\u6597\u62f1"),
        "rules": [
            "dougong cannot be isolated cubes; build stacked bracket blocks, cantilever arms and beam seats under the eave",
            "use at least two colors or material layers for painted bracket blocks when reference supports painted timber",
        ],
        "failure_check": "facade close-up fails if bracket blocks do not visually support the eave",
    },
    {
        "name": "ornamental_lattice_windows",
        "terms": ("lattice", "window", "\u83f1\u82b1", "\u95e8\u7a97", "\u7a97", "\u683c\u5fc3"),
        "rules": [
            "windows need recessed dark glass or interior shadow, outer frame thickness, vertical bars, horizontal bars and diagonal or ornamental bars when named",
            "avoid one simple cross when the request mentions ornamental lattice or historical window patterns",
        ],
        "failure_check": "facade close-up fails if windows read as flat black rectangles with only one cross",
    },
    {
        "name": "stone_balustrade_and_stairs",
        "terms": ("balustrade", "rail", "stair", "\u680f\u6746", "\u697c\u68af", "\u53f0\u9636", "\u6c49\u767d\u7389"),
        "rules": [
            "stairs need individual treads, risers, side cheeks, landing slabs and clear railing openings",
            "stone balustrades need separate posts, caps, panels, relief strips and breaks at stair entrances",
        ],
        "failure_check": "stair close-up fails if stairs are a ramp, a single block, or if railings cross the stair opening",
    },
    {
        "name": "plinth_wall_ground_connection",
        "terms": ("plinth", "terrace", "wall", "\u53f0\u57fa", "\u987b\u5f25\u5ea7", "\u57ce\u5899", "\u5730\u9762"),
        "rules": [
            "ground contact needs a believable base or plinth, not a floating building body",
            "the main body, columns and plinth must physically touch or overlap through hidden support blocks; do not leave visible shadow gaps under the building",
            "historic wall or terrace connections need visible courses, seams, edges and material separation",
        ],
        "failure_check": "overview fails if the building body, columns, base, wall or terrace appear detached or hovering",
    },
]


def _source_text(item: dict[str, Any]) -> str:
    return " ".join(str(item.get(key, "")) for key in ("title", "snippet", "url"))


def _brief_text(brief: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("scene_goal", "relationships", "must_have", "quality_gates", "hard_constraints", "uncertainties"):
        value = brief.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value:
            parts.append(str(value))
    for contract in brief.get("space_contracts", []):
        if isinstance(contract, dict):
            parts.append(" ".join(str(value) for value in contract.values()))
    visual = brief.get("visual_language", {})
    if isinstance(visual, dict):
        parts.append(" ".join(str(value) for value in visual.values()))
    return " ".join(parts)


def _materials_from_sources(text: str, module: str) -> list[str]:
    lower = text.lower()
    defaults = ["stone", "timber", "roof_tile", "metal"] if module == "exterior_architecture" else ["floor_finish", "wall_finish", "ceiling_finish", "glass", "timber"]
    found = [name for name, terms in MATERIAL_HINTS.items() if any(term.lower() in lower for term in terms)]
    return list(dict.fromkeys([*defaults, *found]))


def _signature_feature_rules(text: str, module: str) -> list[dict[str, Any]]:
    if module != "exterior_architecture":
        return []
    lower = text.lower()
    matches = []
    for feature in FEATURE_RULES:
        if any(term.lower() in lower for term in feature["terms"]):
            matches.append({"name": feature["name"], "rules": feature["rules"], "failure_check": feature["failure_check"]})
    return matches


def _geometry_contract(question: str, brief: dict[str, Any], module: str) -> dict[str, Any]:
    text = f"{question} {_brief_text(brief)}".lower()
    components: list[str] = []
    forbidden = [
        "Do not satisfy target identity with generic boxes plus decoration.",
        "Do not leave visible Boolean cutter objects in the exported GLB.",
        "Do not render only close-up fragments; include a full recognizable overview.",
    ]
    if module != "exterior_architecture":
        return {"target_archetype": "interior_space", "required_components": components, "forbidden_shortcuts": forbidden}

    components.extend(
        [
            "continuous ground-contact base or plinth supporting the main body",
            "recognizable primary body mass with real doors/windows/openings",
            "roof system with sloped mass, eaves, ridge lines, underside support and repeated tile detail",
            "front, roof/eave, and weak-connection audit cameras",
        ]
    )
    if any(term in text for term in ("tiananmen", "天安门")):
        components.extend(
            [
                "Tiananmen city platform: white marble xumizuo is only the low base; the red city platform must be a much taller mass above it",
                "five real arched gateway voids through the red city platform, with the center opening largest and no cutter objects left visible",
                "upper pavilion centered on the platform with nine-bay by five-bay rhythm and red column grid",
                "double-eaved xieshan roof built from sloped roof surfaces, lower and upper eaves, main ridge, hip ridges, ridge beasts and yellow tile courses",
                "front identity details: national emblem, portrait/signboard zone, 36 dark lattice windows, lantern row, dougong under eaves and white marble balustrades",
            ]
        )
        forbidden.extend(
            [
                "Do not use the 1.59m xumizuo dimension as the full city-platform height.",
                "Do not model the double-eaved xieshan roof as two flat cube slabs.",
                "Do not export archway cutter spheres/cubes as visible objects.",
            ]
        )
        return {"target_archetype": "tiananmen_gate", "required_components": components, "forbidden_shortcuts": forbidden}
    return {"target_archetype": "generic_exterior_landmark", "required_components": components, "forbidden_shortcuts": forbidden}


def _modeling_recipe(question: str, brief: dict[str, Any], module: str) -> dict[str, Any]:
    text = f"{question} {_brief_text(brief)}".lower()
    recipe = {
        "scale_policy": [
            "Keep each source dimension attached to the component it describes; never reuse a base, trim or ornament dimension as a whole-building dimension.",
            "When exact survey dimensions are missing, preserve the visible hierarchy first: base supports body, body supports roof, openings cut through their parent mass, details sit on top.",
        ],
        "component_translation": [
            "Translate every confirmed or inferred must-have item into named mesh groups, not adjectives in comments.",
            "For each signature item, build at least mass, edge/trim, and repeated-detail layers before materials.",
            "Use object names that match the architectural role so later audit can inspect the scene.",
        ],
        "procedural_helpers_to_write": [
            "build_roof_shell",
            "build_ridge_and_tile_rows",
            "build_column_grid",
            "build_facade_openings",
            "build_stairs_and_balustrades",
            "build_pbr_materials",
            "build_audit_cameras",
        ],
        "material_translation": [
            "Create separate PBR-like materials for structural stone, lacquered timber, roof tile, dark openings/glass, and metal/gold trim.",
            "Use bevels plus procedural noise/bump/color variation; do not rely on flat base colors.",
        ],
        "camera_translation": [
            "Render one full-building orthographic or long-lens overview that proves silhouette and ground contact.",
            "Render close-up audit views for roof/eave, facade/openings, and stair/base connections when those features are requested.",
        ],
    }
    if module == "exterior_architecture" and any(term in text for term in ("tiananmen", "天安门")):
        recipe["component_translation"].extend(
            [
                "Build Tiananmen as two dominant masses first: a tall red city platform over a separate low white marble xumizuo, then the timber pavilion above.",
                "Build the five gateway openings as real structural voids through the red platform using pier segments/arch geometry or applied-and-deleted booleans; center opening must be largest.",
                "Build the double-eaved xieshan roof with sloped roof planes, lower and upper eaves, main ridge, hip ridges, diagonal ridges, upturned corners, ridge ornaments and repeated yellow tile courses.",
                "Build the pavilion facade from a nine-by-five bay rhythm: red column grid, recessed dark wall/window panels, diamond lattice bars, dougong rows under eaves, lantern row, emblem/signboard zone and balustrades.",
            ]
        )
        recipe["procedural_helpers_to_write"].extend(["build_xieshan_roof", "build_arch_gateway_row", "build_linghua_lattice_windows", "build_dougong_band"])
        recipe["audit_requirements"] = [
            "Fail if the red city platform is not visibly taller than the white xumizuo base.",
            "Fail if five arched gateways are only loose objects or painted marks.",
            "Fail if the roof reads as stacked flat boards instead of double-eaved xieshan geometry.",
            "Fail if the front overview does not show platform, pavilion and roof together.",
        ]
    else:
        recipe["audit_requirements"] = [
            "Fail if the requested landmark cannot be recognized from the full-building overview.",
            "Fail if named openings are not real modeled openings.",
            "Fail if named roof or stair systems are represented only by generic blocks.",
        ]
    return recipe


def build_prompt_quality_package(question: str, research: dict[str, Any], brief: dict[str, Any], standard: list[str]) -> dict[str, Any]:
    module = brief.get("generation_module", "interior_space")
    sources = research.get("sources", [])[:10]
    combined = " ".join([question, *(_source_text(item) for item in sources)])
    evidence = [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "usable_for_prompt": (item.get("snippet") or item.get("title") or "")[:500],
        }
        for item in sources[:6]
    ]
    return {
        "purpose": "Convert research into explicit Blender modeling instructions, not just archived references.",
        "identity_lock": {
            "requested_target": question,
            "do_not_replace_target": True,
            "source_count": len(sources),
        },
        "build_order": [
            "freeze target identity and source confidence",
            "block out recognizable massing before small decoration",
            "add structural connections and circulation details",
            "add signature facade, roof, opening and edge details",
            "apply separated realistic materials with roughness, noise and bump",
            "render hero and close-up audit views before export",
        ],
        "detail_targets": EXTERIOR_DETAIL_TARGETS if module == "exterior_architecture" else INTERIOR_DETAIL_TARGETS,
        "signature_feature_rules": _signature_feature_rules(combined, module),
        "material_targets": _materials_from_sources(combined, module),
        "negative_constraints": [
            "no unrelated filler objects unless requested",
            "no white clay final material",
            "no single-color plastic look",
            "no floating slabs, fake painted openings or disconnected parts",
            "no guardrail passing through stairs or entrances",
        ],
        "audit_views": brief.get("delivery_views", []),
        "geometry_contract": _geometry_contract(question, brief, module),
        "modeling_recipe": _modeling_recipe(question, brief, module),
        "quality_standard": standard,
        "evidence_for_prompt": evidence,
    }


def prompt_package_lines(package: dict[str, Any]) -> list[str]:
    lines = [
        "RESEARCH TO MODEL PROMPT PACKAGE:",
        f"- target lock: {package['identity_lock']['requested_target']}",
        "- build order: " + " | ".join(package["build_order"]),
        "- detail targets: " + "; ".join(package["detail_targets"]),
        "- signature feature rules: " + " | ".join(
            f"{item['name']} => " + "; ".join(item["rules"]) for item in package.get("signature_feature_rules", [])
        ),
        "- material targets: " + "; ".join(package["material_targets"]),
        "- negative constraints: " + "; ".join(package["negative_constraints"]),
        "- geometry contract required components: " + "; ".join(package.get("geometry_contract", {}).get("required_components", [])),
        "- geometry contract forbidden shortcuts: " + "; ".join(package.get("geometry_contract", {}).get("forbidden_shortcuts", [])),
        "- Blender modeling recipe scale policy: " + "; ".join(package.get("modeling_recipe", {}).get("scale_policy", [])),
        "- Blender modeling recipe component translation: " + "; ".join(package.get("modeling_recipe", {}).get("component_translation", [])),
        "- Blender modeling recipe procedural helpers to write: " + "; ".join(package.get("modeling_recipe", {}).get("procedural_helpers_to_write", [])),
        "- Blender modeling recipe material translation: " + "; ".join(package.get("modeling_recipe", {}).get("material_translation", [])),
        "- Blender modeling recipe camera translation: " + "; ".join(package.get("modeling_recipe", {}).get("camera_translation", [])),
        "- Blender modeling recipe audit requirements: " + "; ".join(package.get("modeling_recipe", {}).get("audit_requirements", [])),
        "- audit views: " + "; ".join(str(item) for item in package.get("audit_views", [])),
        "- default production standard: " + "; ".join(package["quality_standard"]),
    ]
    evidence = package.get("evidence_for_prompt", [])
    if evidence:
        lines.append("- evidence converted into prompt targets:")
        lines.extend(f"  * {item['title']} :: {item['usable_for_prompt']}" for item in evidence if item.get("usable_for_prompt"))
    failures = [item["failure_check"] for item in package.get("signature_feature_rules", [])]
    if failures:
        lines.append("- close-up failure checks:")
        lines.extend(f"  * {item}" for item in failures)
    return lines
