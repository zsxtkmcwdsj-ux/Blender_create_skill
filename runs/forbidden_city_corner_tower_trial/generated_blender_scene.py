from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def args_after_blender() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "model_output")
    return parser.parse_args(args_after_blender())


def build(output: Path) -> None:
    import bpy
    from mathutils import Vector

    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    scene = bpy.context.scene
    scene.render.resolution_x = 2200
    scene.render.resolution_y = 1400
    scene.render.image_settings.file_format = "PNG"
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.eevee.taa_render_samples = 96
    except Exception:
        scene.render.engine = "BLENDER_EEVEE"

    def mat(name, color, roughness=0.72, metallic=0.0):
        material = bpy.data.materials.new(name)
        material.use_nodes = True
        bsdf = next((node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            bsdf = material.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        return material

    mats = {
        "wall": mat("weathered_gray_brick_city_wall", (0.34, 0.32, 0.28, 1), 0.86),
        "stone": mat("warm_white_stone_balustrade_and_plinth", (0.78, 0.75, 0.67, 1), 0.80),
        "red": mat("imperial_vermilion_lacquered_timber", (0.58, 0.04, 0.015, 1), 0.58),
        "dark": mat("dark_shadow_lattice_wood", (0.10, 0.025, 0.012, 1), 0.70),
        "gold": mat("aged_gilded_copper_finial_and_trim", (0.95, 0.64, 0.14, 1), 0.38, 0.35),
        "roof": mat("yellow_glazed_roof_tiles", (0.98, 0.66, 0.06, 1), 0.45),
        "roof_dark": mat("deep_shadow_under_eave", (0.16, 0.10, 0.02, 1), 0.68),
        "green": mat("painted_green_dougong", (0.04, 0.27, 0.16, 1), 0.62),
        "cyan": mat("painted_cyan_beam_detail", (0.05, 0.34, 0.36, 1), 0.60),
        "glass": mat("dark_recessed_window_glass", (0.015, 0.025, 0.035, 1), 0.30),
        "water": mat("subtle_moat_water", (0.05, 0.11, 0.13, 0.72), 0.28),
    }
    mats["water"].blend_method = "BLEND"

    collections = {}
    for name in ["SITE", "WALLS", "PLINTH_AND_RAILS", "TIMBER_BODY", "ROOF_SYSTEM", "DOUGONG_AND_TRIM", "LIGHTS", "CAMERAS"]:
        col = bpy.data.collections.new(name)
        scene.collection.children.link(col)
        collections[name] = col

    def link(obj, collection):
        for col in obj.users_collection:
            col.objects.unlink(obj)
        collections[collection].objects.link(obj)
        return obj

    def cube(name, loc, scale, material, collection, bevel=0.0):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        obj = bpy.context.object
        obj.name = name
        obj.dimensions = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(material)
        if bevel:
            mod = obj.modifiers.new("small softened edges", "BEVEL")
            mod.width = bevel
            mod.segments = 2
            obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
        return link(obj, collection)

    def cyl(name, loc, radius, depth, material, collection, vertices=32, bevel=False):
        bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(material)
        if bevel:
            obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
        return link(obj, collection)

    def hip_roof(name, width, depth, z, eave_h, ridge_h, material, collection, cross_axis="x"):
        w, d = width / 2, depth / 2
        if cross_axis == "x":
            ridge = [(-w * 0.45, 0, ridge_h), (w * 0.45, 0, ridge_h)]
        else:
            ridge = [(0, -d * 0.45, ridge_h), (0, d * 0.45, ridge_h)]
        verts = [(-w, -d, eave_h), (w, -d, eave_h), (w, d, eave_h), (-w, d, eave_h), *ridge]
        faces = [(0, 1, 5, 4), (1, 2, 5), (2, 3, 4, 5), (3, 0, 4), (0, 3, 2, 1)]
        mesh = bpy.data.meshes.new(name + "_mesh")
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        obj.location.z = z
        obj.data.materials.append(material)
        collections[collection].objects.link(obj)
        obj.modifiers.new("roof weighted normals", "WEIGHTED_NORMAL")
        return obj

    def add_roof_tier(prefix, width, depth, z, eave_h, ridge_h, count):
        roof_a = hip_roof(prefix + "_east_west_hip_roof", width, depth, z, eave_h, ridge_h, mats["roof"], "ROOF_SYSTEM", "x")
        roof_b = hip_roof(prefix + "_north_south_cross_hip_roof", depth * 0.78, width * 0.78, z + 0.02, eave_h + 0.02, ridge_h + 0.02, mats["roof"], "ROOF_SYSTEM", "y")
        cube(prefix + "_dark_under_eave", (0, 0, z + eave_h - 0.18), (width + 0.45, depth + 0.45, 0.18), mats["roof_dark"], "ROOF_SYSTEM", 0.03)
        for row in range(9):
            y = -depth * 0.38 + row * depth * 0.095
            course_z = z + eave_h + 0.10 + abs(y) / depth * 0.45
            for col in range(14):
                x = -width * 0.39 + col * width * 0.06 + (row % 2) * width * 0.03
                cube(prefix + f"_individual_yellow_tile_plate_x_{row:02d}_{col:02d}", (x, y, course_z), (width * 0.032, depth * 0.030, 0.025), mats["roof"], "ROOF_SYSTEM", 0.006)
                cube(prefix + f"_individual_yellow_tile_plate_y_{row:02d}_{col:02d}", (y, x, course_z + 0.01), (depth * 0.030, width * 0.032, 0.025), mats["roof"], "ROOF_SYSTEM", 0.006)
        cube(prefix + "_main_gold_ridge_east_west", (0, 0, z + ridge_h + 0.05), (width * 0.56, 0.10, 0.10), mats["gold"], "ROOF_SYSTEM", 0.02)
        cube(prefix + "_main_gold_ridge_north_south", (0, 0, z + ridge_h + 0.08), (0.10, depth * 0.56, 0.10), mats["gold"], "ROOF_SYSTEM", 0.02)
        for sx, sy in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
            hip = cube(prefix + f"_diagonal_hip_ridge_{sx}_{sy}", (sx * width * 0.19, sy * depth * 0.19, z + eave_h + 0.50), (width * 0.42, 0.07, 0.075), mats["gold"], "ROOF_SYSTEM", 0.015)
            hip.rotation_euler.z = math.atan2(sy * depth, sx * width)
            for beast in range(3):
                cyl(prefix + f"_small_roof_beast_{sx}_{sy}_{beast}", (sx * (width * 0.32 - beast * 0.42), sy * (depth * 0.32 - beast * 0.42), z + eave_h + 0.27 + beast * 0.06), 0.055, 0.16, mats["gold"], "ROOF_SYSTEM", 12, True)
        for i in range(count):
            t = -0.46 + i * (0.92 / max(1, count - 1))
            cube(prefix + f"_raised_tile_rib_x_{i:02d}", (0, t * depth / 2, z + eave_h + 0.08 + abs(t) * 0.30), (width * 0.94, 0.035, 0.045), mats["gold"], "ROOF_SYSTEM", 0.01)
            cube(prefix + f"_raised_tile_rib_y_{i:02d}", (t * width / 2, 0, z + eave_h + 0.08 + abs(t) * 0.30), (0.035, depth * 0.94, 0.045), mats["gold"], "ROOF_SYSTEM", 0.01)
        for sx, sy, rot in [(1, 0, 0), (-1, 0, 0), (0, 1, math.pi / 2), (0, -1, math.pi / 2)]:
            ridge = cube(prefix + f"_upturned_eave_line_{sx}_{sy}", (sx * width * 0.28, sy * depth * 0.28, z + eave_h + 0.16), (width * 0.43 if sy else 0.12, depth * 0.43 if sx else 0.12, 0.12), mats["gold"], "ROOF_SYSTEM", 0.02)
            ridge.rotation_euler.z = rot
        return roof_a, roof_b

    # Site, moat, city wall corner and stone platform.
    cube("dark_neutral_presentation_floor", (0, 0, -0.08), (52, 52, 0.12), mats["wall"], "SITE")
    cube("still_moat_water_band_south", (0, -18, 0.02), (48, 6.0, 0.04), mats["water"], "SITE")
    cube("still_moat_water_band_east", (18, 0, 0.02), (6.0, 48, 0.04), mats["water"], "SITE")
    cube("forbidden_city_south_wall_segment", (0, -8.5, 2.0), (34, 3.0, 4.0), mats["wall"], "WALLS", 0.03)
    cube("forbidden_city_east_wall_segment", (8.5, 0, 2.0), (3.0, 34, 4.0), mats["wall"], "WALLS", 0.03)
    for i in range(26):
        cube(f"individual_brick_course_south_{i:02d}", (-16 + i * 1.28, -10.08, 4.15), (0.94, 0.10, 0.16), mats["wall"], "WALLS")
        cube(f"individual_brick_course_east_{i:02d}", (10.08, -16 + i * 1.28, 4.15), (0.10, 0.94, 0.16), mats["wall"], "WALLS")

    cube("square_xumizuo_plinth_lower", (0, 0, 4.28), (14.4, 14.4, 0.55), mats["stone"], "PLINTH_AND_RAILS", 0.05)
    cube("square_xumizuo_plinth_upper", (0, 0, 4.75), (12.8, 12.8, 0.38), mats["stone"], "PLINTH_AND_RAILS", 0.04)
    cube("stone_contact_block_under_timber_body", (0, 0, 5.06), (9.4, 9.4, 0.30), mats["stone"], "PLINTH_AND_RAILS", 0.035)
    cube("dark_recessed_shadow_under_body_not_gap", (0, 0, 5.23), (8.7, 8.7, 0.12), mats["dark"], "PLINTH_AND_RAILS", 0.015)
    cube("front_stone_landing", (0, -9.4, 4.55), (4.8, 3.0, 0.28), mats["stone"], "PLINTH_AND_RAILS", 0.03)
    for i in range(7):
        cube(f"front_real_stair_tread_{i:02d}", (0, -11.0 - i * 0.48, 4.35 - i * 0.18), (5.0, 0.42, 0.16), mats["stone"], "PLINTH_AND_RAILS", 0.02)
    for x in (-2.85, 2.85):
        cube(f"front_stair_side_cheek_{x}", (x, -12.1, 3.85), (0.28, 4.2, 0.85), mats["stone"], "PLINTH_AND_RAILS", 0.03)

    # Balustrade with an intentional opening at the stair landing.
    for side in ["north", "south", "east", "west"]:
        for i in range(12):
            pos = -5.9 + i * 1.08
            if side == "south" and -2.2 < pos < 2.2:
                continue
            x, y = (pos, 6.65) if side == "north" else (pos, -6.65) if side == "south" else (6.65, pos) if side == "east" else (-6.65, pos)
            cyl(f"stone_balustrade_post_{side}_{i:02d}", (x, y, 5.35), 0.12, 0.98, mats["stone"], "PLINTH_AND_RAILS", 18, True)
            if i < 11:
                nxt = -5.9 + (i + 0.5) * 1.08
                if side == "south" and -2.2 < nxt < 2.2:
                    continue
                px, py = (nxt, 6.65) if side == "north" else (nxt, -6.65) if side == "south" else (6.65, nxt) if side == "east" else (-6.65, nxt)
                cube(f"stone_balustrade_panel_{side}_{i:02d}", (px, py, 5.18), (0.74, 0.10, 0.40) if side in ["north", "south"] else (0.10, 0.74, 0.40), mats["stone"], "PLINTH_AND_RAILS", 0.02)
                cube(f"stone_balustrade_panel_relief_{side}_{i:02d}", (px, py, 5.32), (0.42, 0.035, 0.08) if side in ["north", "south"] else (0.035, 0.42, 0.08), mats["stone"], "PLINTH_AND_RAILS", 0.008)

    # Timber body, columns, windows and lattice.
    cube("red_square_tower_body", (0, 0, 6.55), (8.6, 8.6, 2.7), mats["red"], "TIMBER_BODY", 0.04)
    cube("dark_recessed_interior_shadow", (0, 0, 6.55), (7.5, 7.5, 2.85), mats["dark"], "TIMBER_BODY")

    def tier_support_body(prefix, size, z, height, columns):
        cube(prefix + "_red_upper_timber_core", (0, 0, z), (size, size, height), mats["red"], "TIMBER_BODY", 0.035)
        cube(prefix + "_dark_recessed_upper_shadow", (0, 0, z), (size - 0.75, size - 0.75, height + 0.06), mats["dark"], "TIMBER_BODY", 0.02)
        for side in range(4):
            angle = side * math.pi / 2
            for i in range(columns):
                offset = -size * 0.38 + i * (size * 0.76 / max(1, columns - 1))
                x = math.cos(angle) * size * 0.52 + math.sin(angle) * offset
                y = math.sin(angle) * size * 0.52 - math.cos(angle) * offset
                cyl(prefix + f"_visible_support_column_s{side}_{i}", (x, y, z), 0.105, height + 0.28, mats["red"], "TIMBER_BODY", 24, True)
            cube(prefix + f"_continuous_beam_under_roof_s{side}", (math.cos(angle) * size * 0.55, math.sin(angle) * size * 0.55, z + height / 2 + 0.08), (0.18, size * 1.03, 0.16) if side % 2 == 0 else (size * 1.03, 0.18, 0.16), mats["gold"], "TIMBER_BODY", 0.015)

    tier_support_body("middle_tier", 6.2, 9.05, 1.18, 4)
    tier_support_body("upper_tier", 4.1, 10.95, 0.82, 3)
    for side in range(4):
        angle = side * math.pi / 2
        for i in range(5):
            offset = -3.7 + i * 1.85
            x = math.cos(angle) * 4.45 + math.sin(angle) * offset
            y = math.sin(angle) * 4.45 - math.cos(angle) * offset
            cyl(f"vermilion_outer_column_s{side}_{i}", (x, y, 6.75), 0.16, 3.1, mats["red"], "TIMBER_BODY", 28, True)
        for i in range(3):
            offset = -2.2 + i * 2.2
            x = math.cos(angle) * 4.52 + math.sin(angle) * offset
            y = math.sin(angle) * 4.52 - math.cos(angle) * offset
            panel = cube(f"three_cross_six_bowl_lattice_panel_s{side}_{i}", (x, y, 6.72), (0.08, 1.26, 1.58) if side % 2 == 0 else (1.26, 0.08, 1.58), mats["glass"], "TIMBER_BODY", 0.015)
            for j in range(4):
                delta = -0.45 + j * 0.30
                bx = x + math.sin(angle) * delta
                by = y - math.cos(angle) * delta
                cube(f"lattice_vertical_bar_s{side}_{i}_{j}", (bx, by, 6.72), (0.09, 0.035, 1.62) if side % 2 == 0 else (0.035, 0.09, 1.62), mats["gold"], "TIMBER_BODY", 0.006)
            for j in range(3):
                dz = -0.45 + j * 0.45
                cube(f"lattice_horizontal_bar_s{side}_{i}_{j}", (x, y, 6.72 + dz), (0.10, 1.20, 0.035) if side % 2 == 0 else (1.20, 0.10, 0.035), mats["gold"], "TIMBER_BODY", 0.006)
            for j, tilt in enumerate((-0.72, 0.72)):
                diag = cube(f"diagonal_linghua_lattice_s{side}_{i}_{j}", (x, y, 6.72), (0.075, 1.55, 0.030) if side % 2 == 0 else (1.55, 0.075, 0.030), mats["gold"], "TIMBER_BODY", 0.006)
                diag.rotation_euler.z = angle + tilt

    # Dougong blocks under each eave.
    for level, z, span, count in [("lower", 7.85, 10.8, 18), ("middle", 10.1, 8.2, 14), ("upper", 12.05, 5.7, 10)]:
        for side in range(4):
            angle = side * math.pi / 2
            for i in range(count):
                offset = -span / 2 + i * span / max(1, count - 1)
                x = math.cos(angle) * span / 2 + math.sin(angle) * offset
                y = math.sin(angle) * span / 2 - math.cos(angle) * offset
                cube(f"{level}_green_dougong_block_s{side}_{i:02d}", (x, y, z), (0.30, 0.16, 0.18) if side % 2 == 0 else (0.16, 0.30, 0.18), mats["green"], "DOUGONG_AND_TRIM", 0.01)
                cube(f"{level}_cyan_cantilever_block_s{side}_{i:02d}", (x * 1.02, y * 1.02, z + 0.18), (0.22, 0.12, 0.14) if side % 2 == 0 else (0.12, 0.22, 0.14), mats["cyan"], "DOUGONG_AND_TRIM", 0.01)

    add_roof_tier("lower_compound_roof", 12.4, 12.4, 7.78, 0.0, 1.25, 15)
    add_roof_tier("middle_compound_roof", 9.4, 9.4, 9.75, 0.0, 1.05, 13)
    add_roof_tier("upper_cross_roof", 6.3, 6.3, 11.42, 0.0, 1.20, 11)
    cyl("gilded_copper_central_finial_base", (0, 0, 12.95), 0.38, 0.32, mats["gold"], "ROOF_SYSTEM", 48, True)
    cyl("gilded_copper_central_finial_spire", (0, 0, 13.45), 0.14, 0.95, mats["gold"], "ROOF_SYSTEM", 40, True)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.28, location=(0, 0, 13.95))
    finial = bpy.context.object
    finial.name = "gilded_round_finial_top"
    finial.data.materials.append(mats["gold"])
    link(finial, "ROOF_SYSTEM")

    # Low relief seams and stone panels.
    for i in range(9):
        cube(f"xumizuo_relief_front_panel_{i:02d}", (-5.2 + i * 1.3, -7.24, 4.72), (0.72, 0.045, 0.09), mats["stone"], "PLINTH_AND_RAILS", 0.01)
        cube(f"city_wall_vertical_brick_seam_{i:02d}", (-13.5 + i * 3.1, -10.16, 2.4), (0.035, 0.05, 2.6), mats["stone"], "WALLS")

    # Lighting and cameras.
    bpy.ops.object.light_add(type="SUN", location=(-6, -8, 16))
    sun = bpy.context.object
    sun.name = "late_afternoon_sun"
    sun.data.energy = 3.0
    link(sun, "LIGHTS")
    bpy.ops.object.light_add(type="AREA", location=(-8, -12, 10))
    area = bpy.context.object
    area.name = "large_softbox_for_roof_glaze"
    area.data.energy = 450
    area.data.size = 7
    link(area, "LIGHTS")
    world = bpy.data.worlds.new("black_studio_world")
    world.color = (0.015, 0.016, 0.018)
    scene.world = world

    def aim(obj, target):
        direction = Vector(target) - obj.location
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    def camera(name, loc, target, lens):
        bpy.ops.object.camera_add(location=loc)
        cam = bpy.context.object
        cam.name = name
        cam.data.lens = lens
        aim(cam, target)
        return link(cam, "CAMERAS")

    hero = camera("hero_three_quarter_corner_tower", (18, -22, 13), (0, 0, 8.4), 38)
    roof_detail = camera("roof_ridges_and_finial_detail", (7, -10, 14.2), (0, 0, 11.5), 70)
    facade_detail = camera("dougong_lattice_facade_detail", (0, -13, 7.5), (0, -4.5, 7.0), 70)
    stair_detail = camera("stair_balustrade_opening_detail", (5.5, -13.5, 6.1), (0, -7.2, 4.9), 55)
    scene.camera = hero

    stage = output / "stage_00_forbidden_city_corner_tower.blend"
    blend = output / "forbidden_city_corner_tower.blend"
    glb = output / "forbidden_city_corner_tower.glb"
    previews = [
        (hero, output / "forbidden_city_corner_tower_preview.png"),
        (roof_detail, output / "forbidden_city_corner_tower_roof_detail.png"),
        (facade_detail, output / "forbidden_city_corner_tower_facade_detail.png"),
        (stair_detail, output / "forbidden_city_corner_tower_stair_detail.png"),
    ]
    bpy.ops.wm.save_as_mainfile(filepath=str(stage))
    for cam, path in previews:
        scene.camera = cam
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
    scene.camera = hero
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB", export_yup=True, export_apply=True)

    audit = {
        "target": "故宫角楼 / Forbidden City Corner Tower",
        "scope": "exterior only, reference-informed procedural model",
        "truth_status": "Approximate; based on public architectural descriptions, not survey or photogrammetry accurate.",
        "modeled_features": [
            "city wall corner connection and moat-facing presentation base",
            "square xumizuo-style plinth with stone balustrade and clear stair opening",
            "real front stair treads, side cheeks and landing",
            "vermilion timber body with columns and recessed lattice panels",
            "three compound yellow glazed roof tiers with cross hip-roof masses",
            "individual raised yellow tile plates, main ridges, cross ridges, diagonal hip ridges and small ridge beasts",
            "raised tile ribs, gold ridge lines, upturned eave emphasis and central gilded finial",
            "green/cyan dougong bracket blocks below every roof tier",
            "ornamental lattice windows with vertical, horizontal and diagonal bars",
            "stone balustrade panels with relief strips and intentional stair breaks",
            "separate stone, timber, glass, roof tile, gold and gray brick materials",
            "hero, roof, facade and stair close-up render checks",
        ],
        "quality_checklist": {
            "compound_roof_and_tiles": "pass: separate roof tiers, tile plates, ridges, eave underside and finial are modeled",
            "dougong_brackets": "partial: stacked colored support blocks are present, but still simplified compared with true bracket geometry",
            "ornamental_lattice_windows": "pass: windows have recesses plus vertical, horizontal and diagonal bars",
            "stone_balustrade_and_stairs": "pass: stair treads, landing, posts, panels, relief strips and stair opening are modeled",
            "plinth_wall_ground_connection": "pass: plinth, wall corner and ground/moat context are connected",
        },
        "references": [
            "https://www.dpm.org.cn/explore/building/236522.html",
            "https://epaper.gmw.cn/gmrb/html/2023-12/16/nw.D110000gmrb_20231216_1-10.htm",
            "https://cpc.people.com.cn/n1/2021/0911/c64387-32224136.html",
            "https://www.travelchinaguide.com/attraction/beijing/forbidden-city/corner-towers.htm",
        ],
        "object_count": len(bpy.data.objects),
        "mesh_object_count": len([obj for obj in bpy.data.objects if obj.type == "MESH"]),
        "materials": len(bpy.data.materials),
        "deliverables": {
            "blend": str(blend),
            "glb": str(glb),
            "preview": str(previews[0][1]),
            "roof_detail": str(previews[1][1]),
            "facade_detail": str(previews[2][1]),
            "stair_detail": str(previews[3][1]),
            "stage": str(stage),
        },
    }
    (output / "scene_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


def main() -> None:
    build(parse_args().output.resolve())


if __name__ == "__main__":
    main()
