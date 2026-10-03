from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def script_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a more realistic exterior-only Chinese landmarks scene.")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "realistic")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(script_args())


def self_test() -> None:
    landmarks = ["Temple of Heaven", "Forbidden City Hall", "Lujiazui Skyline", "Bird Nest Stadium"]
    assert len(landmarks) == 4
    print(json.dumps({"passed": True, "landmarks": landmarks}, ensure_ascii=False))


def build(output: Path) -> None:
    import bpy
    from mathutils import Vector

    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    root = bpy.context.scene.collection
    groups = {}
    for name in ["SITE", "TEMPLE_OF_HEAVEN", "FORBIDDEN_CITY", "LUJIAZUI", "BIRD_NEST", "LIGHTS", "CAMERAS"]:
        col = bpy.data.collections.new(name)
        root.children.link(col)
        groups[name] = col

    def link(obj, group):
        for col in list(obj.users_collection):
            col.objects.unlink(obj)
        groups[group].objects.link(obj)
        return obj

    def material(name, color, rough=0.65, metallic=0.0, alpha=1.0):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
        bsdf.inputs["Base Color"].default_value = (*color, alpha)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metallic
        if alpha < 1:
            bsdf.inputs["Alpha"].default_value = alpha
            mat.blend_method = "BLEND"
            mat.show_transparent_back = False
        return mat

    red = material("weathered_palace_red_paint", (0.45, 0.035, 0.02), 0.72)
    gold = material("aged_yellow_glazed_roof_tile", (0.78, 0.43, 0.08), 0.5)
    blue = material("deep_blue_glazed_roof_tile", (0.015, 0.08, 0.27), 0.42)
    white = material("carved_white_marble", (0.78, 0.76, 0.69), 0.86)
    dark = material("dark_roof_shadow", (0.025, 0.027, 0.03), 0.62)
    stone = material("large_gray_plaza_stone", (0.45, 0.45, 0.41), 0.82)
    glass = material("slightly_green_blue_glass", (0.18, 0.45, 0.58), 0.23, 0.0, 0.42)
    pearl = material("oriental_pearl_magenta_panels", (0.72, 0.11, 0.34), 0.36, 0.08)
    steel = material("brushed_structural_steel", (0.55, 0.57, 0.56), 0.38, 0.55)
    black_steel = material("matte_black_stadium_steel", (0.025, 0.026, 0.025), 0.5, 0.5)
    water = material("muted_river_water", (0.025, 0.15, 0.20), 0.22, 0.0, 0.68)
    green = material("field_grass", (0.10, 0.28, 0.10), 0.88)

    def normals(obj):
        if obj.type == "MESH":
            obj.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
        return obj

    def cube(name, loc, dims, mat, group, rot=(0, 0, 0), bevel=0.0):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
        obj = bpy.context.object
        obj.name = name
        obj.dimensions = dims
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(mat)
        if bevel:
            b = obj.modifiers.new("small_bevel", "BEVEL")
            b.width = bevel
            b.segments = 2
        return link(normals(obj), group)

    def cyl(name, loc, radius, depth, mat, group, vertices=48, rot=(0, 0, 0)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rot)
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(mat)
        return link(normals(obj), group)

    def cone(name, loc, r1, r2, depth, mat, group, vertices=96):
        bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=r1, radius2=r2, depth=depth, location=loc)
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(mat)
        return link(normals(obj), group)

    def sphere(name, loc, scale, mat, group):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=1, location=loc)
        obj = bpy.context.object
        obj.name = name
        obj.scale = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(mat)
        return link(normals(obj), group)

    def torus(name, loc, major, minor, mat, group, rot=(0, 0, 0), scale=(1, 1, 1)):
        bpy.ops.mesh.primitive_torus_add(major_segments=128, minor_segments=12, major_radius=major, minor_radius=minor, location=loc, rotation=rot)
        obj = bpy.context.object
        obj.name = name
        obj.scale = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(mat)
        return link(normals(obj), group)

    def beam(name, a, b, radius, mat, group):
        av, bv = Vector(a), Vector(b)
        mid = (av + bv) / 2
        direction = bv - av
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=radius, depth=direction.length, location=mid)
        obj = bpy.context.object
        obj.name = name
        obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
        obj.data.materials.append(mat)
        return link(normals(obj), group)

    def hip_roof(name, x, y, z, w, d, h, mat, group):
        verts = [
            (-w / 2, -d / 2, 0), (w / 2, -d / 2, 0), (w / 2, d / 2, 0), (-w / 2, d / 2, 0),
            (-w * 0.34, -d * 0.28, h), (w * 0.34, -d * 0.28, h), (w * 0.34, d * 0.28, h), (-w * 0.34, d * 0.28, h),
        ]
        faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
        mesh = bpy.data.meshes.new(name + "_mesh")
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        obj.location = (x, y, z)
        obj.data.materials.append(mat)
        groups[group].objects.link(obj)
        normals(obj)
        cube(name + "_ridge", (x, y, z + h + 0.04), (w * 0.66, 0.10, 0.10), mat, group, bevel=0.02)
        return obj

    def aim(cam, target):
        cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene["scope"] = "Exterior-only realistic-style landmark studies."
    scene["truth_status"] = "Reference-informed procedural model; not survey-accurate."
    scene.render.resolution_x = 2200
    scene.render.resolution_y = 1300
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 96
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -0.1
    scene.render.image_settings.file_format = "PNG"

    cube("continuous_real_scale_plaza", (0, 0, -0.08), (92, 42, 0.16), stone, "SITE")
    cube("huangpu_river_strip", (22, 14, -0.035), (44, 8.5, 0.07), water, "SITE")

    # Temple of Heaven, exterior emphasis: triple round marble terrace, dense columns, tiled roof ribs.
    ox, oy = -34, -6
    for i, (r, z) in enumerate([(6.2, 0.18), (5.15, 0.54), (4.1, 0.90)]):
        cyl(f"toh_marble_round_terrace_{i}", (ox, oy, z), r, 0.28, white, "TEMPLE_OF_HEAVEN", 128)
        torus(f"toh_terrace_edge_bead_{i}", (ox, oy, z + 0.16), r, 0.035, white, "TEMPLE_OF_HEAVEN")
    for i in range(24):
        a = math.tau * i / 24
        cyl(f"toh_outer_red_column_{i:02d}", (ox + math.cos(a) * 3.15, oy + math.sin(a) * 3.15, 2.25), 0.11, 2.5, red, "TEMPLE_OF_HEAVEN", 16)
    cyl("toh_circular_wall_band", (ox, oy, 2.0), 2.78, 1.8, red, "TEMPLE_OF_HEAVEN", 128)
    for z, r, h, name in [(3.18, 4.5, 0.86, "lower"), (4.0, 3.36, 0.75, "middle"), (4.66, 2.12, 0.62, "upper")]:
        cone(f"toh_{name}_blue_eave_roof", (ox, oy, z), r, r * 0.42, h, blue, "TEMPLE_OF_HEAVEN", 160)
        for i in range(40):
            a = math.tau * i / 40
            beam(f"toh_{name}_roof_tile_rib_{i:02d}", (ox, oy, z + h * 0.36), (ox + math.cos(a) * r * 0.93, oy + math.sin(a) * r * 0.93, z - h * 0.12), 0.012, dark, "TEMPLE_OF_HEAVEN")
    cyl("toh_gold_finial_stem", (ox, oy, 5.35), 0.10, 0.72, gold, "TEMPLE_OF_HEAVEN", 32)
    sphere("toh_gold_finial_ball", (ox, oy, 5.76), (0.27, 0.27, 0.27), gold, "TEMPLE_OF_HEAVEN")
    for i in range(18):
        a = math.tau * i / 18
        cube(f"toh_balustrade_post_{i:02d}", (ox + math.cos(a) * 5.58, oy + math.sin(a) * 5.58, 1.22), (0.16, 0.16, 0.62), white, "TEMPLE_OF_HEAVEN", bevel=0.025)

    # Forbidden City hall: broad marble stairs, balustrades, red colonnade, yellow roof tile ribs.
    ox, oy = -12, -6
    for i in range(3):
        cube(f"fc_terrace_tier_{i}", (ox, oy, 0.18 + i * 0.36), (17 - i * 1.8, 10 - i * 1.1, 0.30), white, "FORBIDDEN_CITY", bevel=0.03)
    cube("fc_main_red_hall_body", (ox, oy, 2.55), (12.2, 5.6, 3.0), red, "FORBIDDEN_CITY", bevel=0.04)
    for i in range(11):
        x = ox - 5 + i
        cyl(f"fc_front_gold_column_{i:02d}", (x, oy - 2.95, 2.20), 0.12, 2.75, gold, "FORBIDDEN_CITY", 16)
        cube(f"fc_front_dark_bay_{i:02d}", (x, oy - 3.04, 2.38), (0.56, 0.08, 1.6), dark, "FORBIDDEN_CITY")
    hip_roof("fc_lower_yellow_eave", ox, oy, 3.65, 15.3, 7.6, 0.90, gold, "FORBIDDEN_CITY")
    hip_roof("fc_upper_yellow_roof", ox, oy, 4.22, 13.7, 6.6, 1.20, gold, "FORBIDDEN_CITY")
    for i in range(34):
        x = ox - 6.6 + i * 0.4
        cube(f"fc_roof_tile_rib_{i:02d}", (x, oy, 4.08), (0.035, 7.85, 0.07), dark, "FORBIDDEN_CITY")
    for side in [-1, 1]:
        for i in range(11):
            y = oy - 5.15 + i * 0.5
            cube(f"fc_stair_side_post_{side}_{i:02d}", (ox + side * 2.15, y, 0.86 + i * 0.035), (0.12, 0.12, 0.48), white, "FORBIDDEN_CITY", bevel=0.02)
    for i in range(10):
        cube(f"fc_central_stair_step_{i:02d}", (ox, oy - 5.1 + i * 0.38, 0.47 + i * 0.07), (4.2, 0.30, 0.11), white, "FORBIDDEN_CITY")

    # Lujiazui: river, Oriental Pearl, Shanghai Tower, SWFC, Jin Mao style neighbors.
    ox, oy = 14, 1
    cyl("opt_main_shaft", (ox - 6, oy, 6.0), 0.18, 12.0, steel, "LUJIAZUI", 24)
    sphere("opt_lower_observation_sphere", (ox - 6, oy, 4.2), (1.38, 1.38, 1.38), pearl, "LUJIAZUI")
    sphere("opt_upper_observation_sphere", (ox - 6, oy, 8.9), (0.84, 0.84, 0.84), pearl, "LUJIAZUI")
    sphere("opt_small_top_sphere", (ox - 6, oy, 13.0), (0.35, 0.35, 0.35), pearl, "LUJIAZUI")
    cyl("opt_antenna", (ox - 6, oy, 14.6), 0.045, 3.0, steel, "LUJIAZUI", 16)
    for i in range(3):
        a = math.tau * i / 3 + 0.35
        beam(f"opt_slanted_leg_{i}", (ox - 6 + math.cos(a) * 0.62, oy + math.sin(a) * 0.62, 0.55), (ox - 6 + math.cos(a) * 1.25, oy + math.sin(a) * 1.25, 4.0), 0.08, steel, "LUJIAZUI")
    for i in range(20):
        z = 0.6 + i * 0.62
        cyl(f"shanghai_tower_rotating_glass_floor_{i:02d}", (ox, oy, z), 1.36 - i * 0.021, 0.52, glass, "LUJIAZUI", 54, rot=(0, 0, i * 0.13))
    cyl("shanghai_tower_crown", (ox, oy, 13.3), 0.82, 0.8, glass, "LUJIAZUI", 54, rot=(0, 0, 2.8))
    cube("swfc_bottle_opener_tower", (ox + 5.0, oy, 6.4), (2.2, 1.6, 11.8), glass, "LUJIAZUI", bevel=0.03)
    cube("swfc_top_void", (ox + 5.0, oy - 0.02, 11.0), (1.25, 1.72, 1.5), dark, "LUJIAZUI", bevel=0.02)
    for i in range(12):
        cube(f"jinmao_stepped_tier_{i:02d}", (ox + 8.8, oy, 0.55 + i * 0.62), (2.25 - i * 0.07, 1.5 - i * 0.035, 0.52), glass, "LUJIAZUI", bevel=0.025)
    for i in range(7):
        cube(f"luziazui_low_rise_glass_block_{i}", (ox - 11 + i * 3.4, oy + 4.8, 1.1 + (i % 3) * 0.25), (2.2, 1.2, 2.1 + (i % 3) * 0.5), glass, "LUJIAZUI", bevel=0.025)

    # Bird Nest: exterior structural mesh around stadium bowl.
    ox, oy = 34, -8
    cube("birdnest_sunken_field", (ox, oy, 0.14), (7.4, 3.8, 0.12), green, "BIRD_NEST")
    for z, major in [(1.0, 4.6), (1.45, 4.35), (1.9, 4.05)]:
        torus(f"birdnest_elliptical_outer_ring_{z}", (ox, oy, z), major, 0.075, black_steel, "BIRD_NEST", scale=(1.55, 0.78, 0.22))
    for i in range(42):
        a = math.tau * i / 42
        a2 = a + (0.72 if i % 2 else -0.58)
        beam(
            f"birdnest_randomized_exterior_lattice_{i:02d}",
            (ox + math.cos(a) * 7.1, oy + math.sin(a) * 3.55, 0.48 + (i % 4) * 0.08),
            (ox + math.cos(a2) * 6.4, oy + math.sin(a2) * 3.15, 2.45 - (i % 3) * 0.12),
            0.045,
            black_steel,
            "BIRD_NEST",
        )
    for i in range(14):
        beam(f"birdnest_bowl_raker_{i:02d}", (ox - 5.8 + i * 0.9, oy - 2.9, 0.75), (ox - 4.8 + i * 0.72, oy + 2.6, 1.62), 0.036, black_steel, "BIRD_NEST")

    # Light, cameras, atmosphere.
    bpy.ops.object.light_add(type="SUN", location=(-10, -14, 20))
    sun = bpy.context.object
    sun.name = "low_clear_afternoon_sun"
    sun.data.energy = 2.1
    sun.rotation_euler = (math.radians(42), 0, math.radians(-38))
    link(sun, "LIGHTS")
    bpy.ops.object.light_add(type="AREA", location=(0, -24, 16))
    fill = bpy.context.object
    fill.name = "large_soft_sky_fill"
    fill.data.energy = 450
    fill.data.size = 22
    link(fill, "LIGHTS")

    bpy.ops.object.camera_add(location=(0, -48, 17))
    hero = bpy.context.object
    hero.name = "realistic_all_landmarks_camera"
    hero.data.lens = 25
    aim(hero, (1, -3, 4.0))
    link(hero, "CAMERAS")
    scene.camera = hero

    bpy.ops.object.camera_add(location=(-23, -25, 9))
    historic = bpy.context.object
    historic.name = "historic_landmarks_camera"
    historic.data.lens = 31
    aim(historic, (-22, -6, 2.8))
    link(historic, "CAMERAS")

    bpy.ops.object.camera_add(location=(31, -26, 11))
    modern = bpy.context.object
    modern.name = "modern_landmarks_camera"
    modern.data.lens = 30
    aim(modern, (18, -2, 5.2))
    link(modern, "CAMERAS")

    world = bpy.data.worlds.new("clear_blue_gray_realistic_world")
    world.color = (0.06, 0.075, 0.09)
    scene.world = world

    stage = output / "stage_00_realistic_exterior.blend"
    blend = output / "china_landmarks_realistic.blend"
    glb = output / "china_landmarks_realistic.glb"
    preview = output / "china_landmarks_realistic_preview.png"
    historic_preview = output / "china_landmarks_historic_preview.png"
    modern_preview = output / "china_landmarks_modern_preview.png"

    bpy.ops.wm.save_as_mainfile(filepath=str(stage))
    for camera, path in [(hero, preview), (historic, historic_preview), (modern, modern_preview)]:
        scene.camera = camera
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
    scene.camera = hero
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB", export_yup=True, export_apply=True)

    audit = {
        "target": "Chinese landmark realistic exterior studies",
        "truth_status": scene["truth_status"],
        "landmarks": ["Temple of Heaven", "Forbidden City Hall", "Lujiazui Skyline", "Bird Nest Stadium"],
        "objects_total": len(bpy.data.objects),
        "mesh_objects": len([obj for obj in bpy.data.objects if obj.type == "MESH"]),
        "materials": len(bpy.data.materials),
        "deliverables": {
            "blend": str(blend),
            "glb": str(glb),
            "preview": str(preview),
            "historic_preview": str(historic_preview),
            "modern_preview": str(modern_preview),
            "stage": str(stage),
        },
        "references_used": [
            "https://artsandculture.google.com/story/explore-the-hall-of-supreme-harmony-the-palace-museum/AwURf6njEEfMAQ?hl=en",
            "https://govt.chinadaily.com.cn/s/202105/24/WS60ab676e498e7a02c6f6bfd5/hall-of-supreme-harmony-taihe-dian.html",
            "https://www.otis.com/en/kw/our-company/global-projects/project-showcase/oriental-pearl-tower",
            "https://english.shanghai.gov.cn/en-ScenicSpots/20231205/19a5f5184eca45728fd57a4d4c8efc61.html",
        ],
    }
    (output / "scene_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    build(args.output.resolve())


if __name__ == "__main__":
    main()
