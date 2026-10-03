from __future__ import annotations

import re


def extract_python_code(text: str) -> str:
    value = (text or "").strip()
    match = re.search(r"```(?:python|py)?\s*(.*?)```", value, flags=re.I | re.S)
    return (match.group(1) if match else value).strip()


def _drop_wm_append_link_calls(code: str) -> str:
    lines: list[str] = []
    skipping = False
    depth = 0
    for line in code.splitlines():
        if not skipping and re.match(r"^\s*bpy\.ops\.wm\.(?:append|link)\(", line):
            skipping = True
            depth = line.count("(") - line.count(")")
            if depth <= 0:
                skipping = False
            continue
        if skipping:
            depth += line.count("(") - line.count(")")
            if depth <= 0:
                skipping = False
            continue
        lines.append(line)
    return "\n".join(lines)


def sanitize_blender_code(code: str) -> str:
    collection_parent = re.compile(r"^\s*\w+\.parent\s*=\s*\w+_coll\s*$")
    cleaned = _drop_wm_append_link_calls(code)
    cleaned = "\n".join(line for line in cleaned.splitlines() if not collection_parent.match(line))
    join_replacement = (
        "    bpy.ops.object.select_all(action='DESELECT')\n"
        "    for obj in objects:\n"
        "        obj.select_set(True)\n"
        "    bpy.context.view_layer.objects.active = objects[0]\n"
        "    bpy.ops.object.join()"
    )
    cleaned = cleaned.replace(
        "    ctx = bpy.context.copy()\n"
        "    ctx['active_object'] = objects[0]\n"
        "    ctx['selected_editable_objects'] = objects\n"
        "    bpy.ops.object.join(ctx)",
        join_replacement,
    )
    cleaned = cleaned.replace(
        "    ctx = bpy.context.copy()\n"
        "    ctx['selected_editable_objects'] = objects\n"
        "    ctx['active_object'] = objects[0]\n"
        "    bpy.ops.object.join(ctx)",
        join_replacement,
    )
    cleaned = cleaned.replace("bpy.ops.object.join(ctx)", "bpy.ops.object.join()")
    cleaned = cleaned.replace(
        "    # Convert to mesh\n"
        "    bpy.context.view_layer.objects.active = curve_obj\n"
        "    bpy.ops.object.convert(target='MESH')\n"
        "    \n"
        "    # Extrude\n"
        "    bpy.ops.object.mode_set(mode='EDIT')",
        "    # Convert to mesh\n"
        "    bpy.ops.object.select_all(action='DESELECT')\n"
        "    curve_obj.select_set(True)\n"
        "    bpy.context.view_layer.objects.active = curve_obj\n"
        "    bpy.ops.object.convert(target='MESH')\n"
        "    curve_obj = bpy.context.view_layer.objects.active\n"
        "    \n"
        "    # Extrude\n"
        "    bpy.ops.object.mode_set(mode='EDIT')",
    )
    cleaned = re.sub(
        r"^(\s*)bsdf = mat\.node_tree\.nodes\[['\"]Principled BSDF['\"]\]",
        r"\1bsdf = next((node for node in mat.node_tree.nodes if node.type == 'BSDF_PRINCIPLED'), None)",
        cleaned,
        flags=re.M,
    )
    cleaned = cleaned.replace("ShaderNodeNoiseTexture", "ShaderNodeTexNoise")
    cleaned = re.sub(r"^\s*export_colors\s*=\s*(?:True|False),?\s*$", "", cleaned, flags=re.M)
    return cleaned.strip() + "\n"


def blender_script_prompt(skill_prompt: str) -> str:
    return f"""
Write one complete Blender Python script from the modeling brief below.

Hard requirements:
- Return Python code only.
- The script must run in Blender background mode.
- It must accept --output after Blender's -- separator.
- It must create an editable .blend, a .glb, at least one preview .png, and scene_audit.json.
- Follow the research-to-model prompt package exactly: target lock, build order, detail targets, material targets, negative constraints, and audit views.
- Treat any geometry contract in the prompt package as hard requirements. If a requested component is hard to model, create a simplified but structurally correct version instead of omitting it.
- Convert every signature feature rule into real geometry. Do not satisfy named historical details with symbolic cubes or flat color patches.
- Before writing code, make a target-specific blockout plan in code comments: base/plinth, main body, openings, roof topology, structural supports, small repeated details, cameras.
- First-pass preflight: the script you output must already avoid the known structural failure modes: reused low base dimensions as full platforms, flat cube slabs for named sloped/hipped roof types, visible Boolean cutter leftovers, and overview cameras cropped too tightly to prove the whole landmark.
- For each named feature, create at least three visible layers of geometry where applicable, such as mass + trim + small repeated detail.
- Prefer target-specific procedural helpers for repeated architecture: roof-shell builders, ridge/tile row builders, column-grid builders, balustrade/stair builders, and facade-opening builders. Avoid one-off placeholder primitives for signature forms.
- Structural numbers must keep their source meaning. Example: a low base dimension cannot be reused as the full height of a city wall or platform.
- If the brief names roof tiles, lattice windows, dougong, stairs, balustrades, plinths, or wall connections, the close-up camera must show those details clearly.
- Build structural geometry first, then details, then materials, then lighting/cameras.
- Do not append or link external .blend assets unless the brief provides a real local file path; never call bpy.ops.wm.append/link with empty filepath, directory or filename.
- Do not assign an Object's parent to a Collection. Blender object.parent must be another Object; for collections use collection.objects.link(obj) or leave the object in the active scene collection.
- Use Blender 5 compatible operators; do not call bpy.ops.object.join(ctx), select objects and call bpy.ops.object.join() with no positional context argument.
- Before mesh operators in background mode, explicitly select the target object, set it active, and enter EDIT mode.
- Find shader nodes by type, not display name; do not assume mat.node_tree.nodes["Principled BSDF"] exists.
- Use Blender 5 node ids such as ShaderNodeTexNoise, not ShaderNodeNoiseTexture.
- Do not pass obsolete glTF exporter args such as export_colors.
- Do not make a white clay final model.
- Do not add unrelated filler objects.
- Use procedural PBR-like materials with separate colors, roughness, noise or bump where relevant.
- Name collections and objects semantically.
- Export a browser-visible GLB with material base colors.
- scene_audit.json must include modeled_features and a quality_checklist with pass/fail notes for the signature feature rules and close-up failure checks.
- scene_audit.json must also list geometry_contract_checks with pass/fail notes for every required geometry-contract component.
- scene_audit.json must be strict: mark fail if the target's main silhouette is not recognizable, if required openings are only loose placeholder objects instead of real visible voids, if roof tiers are flat slabs instead of sloped/hipped masses, or if camera views crop out the full building.

Modeling brief:
{skill_prompt}
""".strip()
