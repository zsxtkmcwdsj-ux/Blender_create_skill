from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


LANDMARKS = [
    "Temple of Heaven",
    "Forbidden City Hall",
    "Oriental Pearl Tower",
    "Shanghai Tower",
    "CCTV Headquarters",
    "Bird Nest Stadium",
    "HZMB Bridge",
    "Suzhou Museum New",
]


def script_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build exterior-only Chinese landmark concept scene in Blender.")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(script_args())


def self_test() -> None:
    assert len(LANDMARKS) == 8
    assert len(set(LANDMARKS)) == len(LANDMARKS)
    assert all(name and name == name.strip() for name in LANDMARKS)
    print(json.dumps({"passed": True, "landmarks": LANDMARKS}, ensure_ascii=False))


def build_scene(output: Path) -> None:
    import bpy
    from mathutils import Vector

    output.mkdir(parents=True, exist_ok=True)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.name != "Collection":
            bpy.data.collections.remove(collection)

    root = bpy.context.scene.collection
    groups = {}
    for name in ["GROUND", "LANDMARKS", "BRIDGES", "DETAILS", "LIGHTS", "CAMERAS"]:
        collection = bpy.data.collections.new(name)
        root.children.link(collection)
        groups[name] = collection

    def link(obj, group="LANDMARKS"):
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        groups[group].objects.link(obj)
        return obj

    def mat(name, color, rough=0.7, metallic=0.0, alpha=1.0):
        material = bpy.data.materials.new(name)
        material.use_nodes = True
        bsdf = next(node for node in material.node_tree.nodes if node.bl_idname == "ShaderNodeBsdfPrincipled")
        bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], alpha)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metallic
        if alpha < 1:
            bsdf.inputs["Alpha"].default_value = alpha
            material.blend_method = "BLEND"
            material.use_screen_refraction = True
        return material

    RED = mat("CN_palace_red", (0.55, 0.04, 0.025), 0.62)
    GOLD = mat("CN_glazed_gold_roof", (0.95, 0.64, 0.10), 0.42)
    BLUE = mat("CN_cobalt_blue_roof", (0.02, 0.18, 0.58), 0.46)
    WHITE = mat("CN_white_plaster", (0.86, 0.84, 0.76), 0.82)
    STONE = mat("CN_light_stone", (0.52, 0.52, 0.48), 0.84)
    DARK = mat("CN_dark_tile", (0.05, 0.06, 0.065), 0.68)
    GLASS = mat("CN_blue_glass", (0.22, 0.55, 0.72), 0.2, 0.0, 0.5)
    PINK = mat("CN_oriental_pearl_cladding", (0.82, 0.20, 0.45), 0.34, 0.15)
    STEEL = mat("CN_brushed_steel", (0.64, 0.66, 0.65), 0.32, 0.6)
    DARK_STEEL = mat("CN_dark_steel", (0.08, 0.085, 0.09), 0.38, 0.65)
    WATER = mat("CN_water", (0.04, 0.22, 0.32), 0.16, 0.0, 0.72)
    ROAD = mat("CN_bridge_road", (0.12, 0.13, 0.14), 0.7)
    GREEN = mat("CN_landscape_green", (0.12, 0.28, 0.12), 0.88)

    def add_weighted_normals(obj):
        if obj.type == "MESH":
            obj.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
        return obj

    def cube(name, loc, dims, material, group="LANDMARKS", rot=(0, 0, 0), bevel=0):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
        obj = bpy.context.object
        obj.name = name
        obj.dimensions = dims
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(material)
        if bevel:
            modifier = obj.modifiers.new("edge_bevel", "BEVEL")
            modifier.width = bevel
            modifier.segments = 2
        add_weighted_normals(obj)
        return link(obj, group)

    def cyl(name, loc, radius, depth, material, group="LANDMARKS", vertices=32, rot=(0, 0, 0)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rot)
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(material)
        add_weighted_normals(obj)
        return link(obj, group)

    def cone(name, loc, radius1, radius2, depth, material, group="LANDMARKS", vertices=48):
        bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius1, radius2=radius2, depth=depth, location=loc)
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(material)
        add_weighted_normals(obj)
        return link(obj, group)

    def sphere(name, loc, scale, material, group="LANDMARKS"):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1, location=loc)
        obj = bpy.context.object
        obj.name = name
        obj.scale = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(material)
        add_weighted_normals(obj)
        return link(obj, group)

    def torus(name, loc, major_radius, minor_radius, material, group="LANDMARKS", rot=(0, 0, 0), scale=(1, 1, 1)):
        bpy.ops.mesh.primitive_torus_add(major_segments=96, minor_segments=10, major_radius=major_radius, minor_radius=minor_radius, location=loc, rotation=rot)
        obj = bpy.context.object
        obj.name = name
        obj.scale = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(material)
        add_weighted_normals(obj)
        return link(obj, group)

    def beam_between(name, start, end, radius, material, group="DETAILS"):
        start_v, end_v = Vector(start), Vector(end)
        mid = (start_v + end_v) / 2
        direction = end_v - start_v
        bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=radius, depth=direction.length, location=mid)
        obj = bpy.context.object
        obj.name = name
        obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
        obj.data.materials.append(material)
        add_weighted_normals(obj)
        return link(obj, group)

    def roof_wedge(name, x, y, z, width, depth, height, material, group="LANDMARKS"):
        verts = [
            (-width / 2, -depth / 2, 0),
            (width / 2, -depth / 2, 0),
            (width / 2, depth / 2, 0),
            (-width / 2, depth / 2, 0),
            (0, -depth / 2, height),
            (0, depth / 2, height),
        ]
        faces = [(0, 1, 2, 3), (0, 4, 1), (3, 2, 5), (0, 3, 5, 4), (1, 4, 5, 2)]
        mesh = bpy.data.meshes.new(name + "_mesh")
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        obj.location = (x, y, z)
        obj.data.materials.append(material)
        add_weighted_normals(obj)
        groups[group].objects.link(obj)
        return obj

    def label(name, body, loc, size=0.38):
        bpy.ops.object.text_add(location=loc, rotation=(math.radians(90), 0, 0))
        obj = bpy.context.object
        obj.name = name
        obj.data.body = body
        obj.data.size = size
        obj.data.align_x = "CENTER"
        obj.data.align_y = "CENTER"
        obj.data.extrude = 0.012
        obj.data.materials.append(DARK)
        return link(obj, "DETAILS")

    def aim(camera, target):
        camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene["workflow"] = "blender-mcp-reference-modeling"
    scene["scope"] = "Exterior-only concept set of iconic Chinese landmarks."
    scene["truth_status"] = "Conceptual exterior massing, not survey-accurate reproduction."
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1100
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.look = "AgX - Medium High Contrast"

    cube("site_plaza", (0, 0, -0.08), (92, 34, 0.16), STONE, "GROUND")
    cube("north_water_band", (0, 12.5, -0.03), (92, 6, 0.08), WATER, "GROUND")
    for x in [-36, -24, -12, 0, 12, 24, 36]:
        cyl(f"site_tree_{x}", (x, -15, 1.2), 0.12, 2.4, DARK, "GROUND", 10)
        sphere(f"site_tree_crown_{x}", (x, -15, 2.55), (0.85, 0.85, 0.7), GREEN, "GROUND")

    # Temple of Heaven: round terraces, red timber ring, triple blue roof and finial.
    ox, oy = -38, -5
    for i, (r, z) in enumerate([(4.8, 0.15), (4.05, 0.5), (3.3, 0.85)]):
        cyl(f"temple_heaven_terrace_{i+1}", (ox, oy, z), r, 0.28, STONE, vertices=80)
    cyl("temple_heaven_red_drum", (ox, oy, 2.1), 2.45, 2.2, RED, vertices=64)
    for i in range(16):
        angle = math.tau * i / 16
        cyl(f"temple_heaven_column_{i+1:02d}", (ox + math.cos(angle) * 2.8, oy + math.sin(angle) * 2.8, 2.0), 0.12, 2.2, RED, vertices=12)
    cone("temple_heaven_lower_roof", (ox, oy, 3.25), 4.0, 1.8, 1.0, BLUE, vertices=96)
    cone("temple_heaven_middle_roof", (ox, oy, 4.0), 3.0, 1.25, 0.86, BLUE, vertices=96)
    cone("temple_heaven_upper_roof", (ox, oy, 4.65), 2.1, 0.4, 0.75, BLUE, vertices=96)
    cyl("temple_heaven_gold_finial", (ox, oy, 5.35), 0.12, 0.7, GOLD, vertices=24)
    label("label_temple_heaven", "Temple of Heaven", (ox, oy - 5.6, 0.05))

    # Forbidden City Hall: white terrace, red hall, yellow hip roofs and front stair.
    ox, oy = -25, -4
    cube("forbidden_terrace_base", (ox, oy, 0.3), (9.6, 6.0, 0.6), STONE)
    cube("forbidden_main_hall", (ox, oy, 2.1), (7.5, 4.2, 2.9), RED, bevel=0.04)
    for x in [-28.2, -27.0, -25.8, -24.6, -23.4, -22.2]:
        cyl(f"forbidden_front_column_{x}", (x, oy - 2.22, 1.9), 0.12, 2.5, GOLD, vertices=14)
    roof_wedge("forbidden_upper_roof", ox, oy, 3.55, 9.2, 5.5, 1.3, GOLD)
    roof_wedge("forbidden_lower_eave", ox, oy, 3.25, 10.2, 6.4, 0.75, GOLD)
    for i in range(5):
        cube(f"forbidden_front_stair_{i+1}", (ox, oy - 3.25 - i * 0.34, 0.25 + i * 0.13), (2.8, 0.3, 0.14), STONE)
    label("label_forbidden_city", "Forbidden City Hall", (ox, oy - 5.7, 0.05))

    # Shanghai Pudong pair: Oriental Pearl plus Shanghai Tower.
    ox, oy = -8, -4
    cyl("oriental_pearl_lower_leg_a", (ox - 0.55, oy, 3.0), 0.12, 6.0, STEEL, vertices=12)
    cyl("oriental_pearl_lower_leg_b", (ox + 0.55, oy, 3.0), 0.12, 6.0, STEEL, vertices=12)
    cyl("oriental_pearl_spire", (ox, oy, 7.2), 0.16, 12.5, STEEL, vertices=16)
    sphere("oriental_pearl_lower_sphere", (ox, oy, 3.8), (1.25, 1.25, 1.25), PINK)
    sphere("oriental_pearl_upper_sphere", (ox, oy, 8.1), (0.82, 0.82, 0.82), PINK)
    sphere("oriental_pearl_tip_sphere", (ox, oy, 12.6), (0.36, 0.36, 0.36), PINK)
    cyl("oriental_pearl_needle", (ox, oy, 14.1), 0.055, 2.4, STEEL, vertices=12)
    label("label_oriental_pearl", "Oriental Pearl", (ox, oy - 4.0, 0.05), 0.32)

    ox = -1
    for i in range(22):
        z = 0.35 + i * 0.48
        radius = 1.25 - i * 0.022
        cyl(f"shanghai_tower_twist_floor_{i+1:02d}", (ox, oy, z), radius, 0.42, GLASS, vertices=36, rot=(0, 0, i * 0.11))
    cyl("shanghai_tower_core", (ox, oy, 6.0), 0.22, 11.4, STEEL, vertices=16)
    label("label_shanghai_tower", "Shanghai Tower", (ox, oy - 3.6, 0.05), 0.32)

    # CCTV Headquarters: leaning twin towers and top cantilever loop.
    ox, oy = 12, -4
    cube("cctv_left_leaning_tower", (ox - 1.9, oy, 4.8), (1.7, 2.2, 9.2), GLASS, rot=(0, math.radians(-10), 0), bevel=0.05)
    cube("cctv_right_leaning_tower", (ox + 1.9, oy, 4.8), (1.7, 2.2, 9.2), GLASS, rot=(0, math.radians(10), 0), bevel=0.05)
    cube("cctv_top_bridge", (ox, oy, 9.45), (5.6, 2.2, 1.35), GLASS, bevel=0.05)
    cube("cctv_lower_link", (ox, oy, 1.1), (5.0, 2.0, 0.6), DARK_STEEL, bevel=0.03)
    for side in [-1, 1]:
        for j in range(5):
            beam_between(f"cctv_diagrid_{side}_{j}", (ox + side * 2.6, oy - 1.12, 1.4 + j * 1.6), (ox + side * 1.2, oy - 1.12, 2.5 + j * 1.6), 0.035, STEEL)
    label("label_cctv", "CCTV Headquarters", (ox, oy - 4.0, 0.05), 0.32)

    # Bird Nest Stadium: oval rings and crossing exterior steel ribs.
    ox, oy = 25, -5
    for i, z in enumerate([0.9, 1.35, 1.8]):
        torus(f"bird_nest_oval_ring_{i+1}", (ox, oy, z), 3.2, 0.08, DARK_STEEL, scale=(1.45, 0.78, 0.22))
    for i in range(28):
        angle = math.tau * i / 28
        x1 = ox + math.cos(angle) * 4.6
        y1 = oy + math.sin(angle) * 2.45
        x2 = ox + math.cos(angle + 0.75) * 4.2
        y2 = oy + math.sin(angle + 0.75) * 2.25
        beam_between(f"bird_nest_cross_beam_{i+1:02d}", (x1, y1, 0.55), (x2, y2, 2.35), 0.04, DARK_STEEL)
    cube("bird_nest_inner_field", (ox, oy, 0.08), (5.2, 2.7, 0.08), GREEN)
    label("label_bird_nest", "Bird Nest Stadium", (ox, oy - 4.6, 0.05), 0.32)

    # Hong Kong-Zhuhai-Macao Bridge: sea viaduct, two pylons and cable fan.
    ox, oy = 36, 7
    cube("hzmb_sea_patch", (ox, oy, -0.04), (20, 7.5, 0.06), WATER, "BRIDGES")
    cube("hzmb_road_deck", (ox, oy, 0.72), (18.5, 0.65, 0.22), ROAD, "BRIDGES")
    for px in [ox - 5.5, ox + 5.5]:
        cyl(f"hzmb_pylon_left_{px}", (px - 0.28, oy, 2.5), 0.08, 3.6, WHITE, "BRIDGES", vertices=12)
        cyl(f"hzmb_pylon_right_{px}", (px + 0.28, oy, 2.5), 0.08, 3.6, WHITE, "BRIDGES", vertices=12)
        cube(f"hzmb_pylon_cross_{px}", (px, oy, 4.15), (0.9, 0.16, 0.16), WHITE, "BRIDGES")
        for k in range(5):
            offset = 1.2 + k * 0.9
            beam_between(f"hzmb_cable_l_{px}_{k}", (px, oy, 4.0 - k * 0.12), (px - offset, oy, 0.9), 0.015, STEEL, "BRIDGES")
            beam_between(f"hzmb_cable_r_{px}_{k}", (px, oy, 4.0 - k * 0.12), (px + offset, oy, 0.9), 0.015, STEEL, "BRIDGES")
    label("label_hzmb", "HZMB Bridge", (ox, oy - 4.7, 0.05), 0.32)

    # Suzhou Museum New: white walls, black folded roofs, water court.
    ox, oy = -33, 9
    cube("suzhou_museum_wall_main", (ox, oy, 1.2), (7.0, 3.5, 2.4), WHITE, bevel=0.03)
    roof_wedge("suzhou_museum_folded_roof_a", ox - 1.8, oy, 2.45, 3.8, 4.0, 0.9, DARK)
    roof_wedge("suzhou_museum_folded_roof_b", ox + 1.8, oy, 2.45, 3.8, 4.0, 0.9, DARK)
    cube("suzhou_museum_glass_entry", (ox, oy - 1.82, 1.2), (2.2, 0.08, 1.65), GLASS)
    cube("suzhou_museum_water_court", (ox, oy + 3.4, 0.04), (6.6, 2.0, 0.06), WATER)
    for x in [ox - 2.8, ox, ox + 2.8]:
        cube(f"suzhou_museum_courtyard_wall_{x}", (x, oy + 4.5, 1.1), (1.8, 0.16, 2.2), WHITE)
    label("label_suzhou_museum", "Suzhou Museum New", (ox, oy - 3.4, 0.05), 0.32)

    # Site signage: tells viewers the scene is an exterior concept collection.
    label("label_scene_title", "China Landmark Exteriors - Concept Massing Set", (0, -17.3, 0.05), 0.55)

    bpy.ops.object.light_add(type="SUN", location=(0, -8, 16))
    sun = bpy.context.object
    sun.name = "soft_afternoon_sun"
    sun.data.energy = 2.4
    sun.rotation_euler = (math.radians(38), 0, math.radians(-32))
    link(sun, "LIGHTS")
    bpy.ops.object.light_add(type="AREA", location=(0, -10, 15))
    fill = bpy.context.object
    fill.name = "wide_sky_fill"
    fill.data.energy = 550
    fill.data.size = 18
    link(fill, "LIGHTS")

    bpy.ops.object.camera_add(location=(4, -58, 24))
    hero = bpy.context.object
    hero.name = "hero_camera_all_landmarks"
    hero.data.lens = 22
    aim(hero, (0, -1.5, 4.0))
    link(hero, "CAMERAS")
    scene.camera = hero

    bpy.ops.object.camera_add(location=(-46, -22, 13))
    west = bpy.context.object
    west.name = "camera_historic_cluster"
    west.data.lens = 34
    aim(west, (-28, -3, 2.8))
    link(west, "CAMERAS")

    bpy.ops.object.camera_add(location=(41, -18, 11))
    east = bpy.context.object
    east.name = "camera_modern_and_bridge"
    east.data.lens = 36
    aim(east, (18, -2, 4.0))
    link(east, "CAMERAS")

    world = bpy.data.worlds.new("china_landmarks_soft_day_world")
    world.color = (0.055, 0.075, 0.095)
    scene.world = world

    blend_path = output / "china_landmarks_exterior.blend"
    glb_path = output / "china_landmarks_exterior.glb"
    preview_path = output / "china_landmarks_exterior_preview.png"
    side_preview_path = output / "china_landmarks_exterior_modern_preview.png"

    bpy.ops.wm.save_as_mainfile(filepath=str(output / "stage_00_blockout.blend"))

    scene.camera = hero
    scene.render.filepath = str(preview_path)
    bpy.ops.render.render(write_still=True)

    scene.camera = east
    scene.render.filepath = str(side_preview_path)
    bpy.ops.render.render(write_still=True)

    scene.camera = hero
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.export_scene.gltf(filepath=str(glb_path), export_format="GLB", export_yup=True, export_apply=True)

    audit = {
        "target": "China landmark exterior concept collection",
        "truth_status": scene["truth_status"],
        "landmarks": LANDMARKS,
        "objects_total": len(bpy.data.objects),
        "mesh_objects": len([obj for obj in bpy.data.objects if obj.type == "MESH"]),
        "materials": len(bpy.data.materials),
        "features": {
            "exterior_only": True,
            "no_interior_rooms": True,
            "semantic_collections": True,
            "editable_blend": True,
            "glb_export": True,
            "preview_renders": True,
        },
        "deliverables": {
            "blend": str(blend_path),
            "glb": str(glb_path),
            "preview": str(preview_path),
            "modern_preview": str(side_preview_path),
            "stage_checkpoint": str(output / "stage_00_blockout.blend"),
        },
        "limitations": [
            "Concept exterior massing only; not survey-accurate.",
            "Procedural Blender lighting and transparent materials may not match GLB exactly.",
        ],
    }
    (output / "scene_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    build_scene(args.output.resolve())


if __name__ == "__main__":
    main()
