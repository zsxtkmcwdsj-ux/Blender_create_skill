from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path


def args_after_blender() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a detailed exterior model of Qiniandian in Blender.")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(args_after_blender())


def self_test() -> None:
    assert 24 + 12 + 12 == 48
    print(json.dumps({"passed": True, "target": "Hall of Prayer for Good Harvests exterior"}, ensure_ascii=False))


WEB_BASE_COLORS = {
    "slightly_warm_hanbaiyu_marble": [0.76, 0.74, 0.68, 1],
    "aged_vermilion_lacquered_wood": [0.48, 0.035, 0.018, 1],
    "deep_shadow_red_wood": [0.20, 0.012, 0.008, 1],
    "aged_gilded_roof_finial": [0.95, 0.62, 0.12, 1],
    "deep_cobalt_blue_glazed_tile": [0.012, 0.060, 0.210, 1],
    "blue_tile_highlight_edges": [0.035, 0.145, 0.42, 1],
    "painted_green_dougong": [0.03, 0.22, 0.12, 1],
    "painted_cyan_beam_detail": [0.06, 0.28, 0.32, 1],
    "painted_ochre_bracket_detail": [0.56, 0.28, 0.055, 1],
    "large_gray_stone_paving": [0.42, 0.42, 0.39, 1],
}


def patch_glb_base_colors(path: Path) -> None:
    data = path.read_bytes()
    magic, version, _ = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2:
        raise ValueError(f"not a GLB v2 file: {path}")
    json_len, json_type = struct.unpack_from("<II", data, 12)
    if json_type != 0x4E4F534A:
        raise ValueError(f"first GLB chunk is not JSON: {path}")
    json_start = 20
    json_end = json_start + json_len
    doc = json.loads(data[json_start:json_end].decode("utf-8"))
    for mat in doc.get("materials", []):
        color = WEB_BASE_COLORS.get(mat.get("name", ""))
        if color:
            mat.setdefault("pbrMetallicRoughness", {})["baseColorFactor"] = color
    encoded = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded += b" " * ((4 - len(encoded) % 4) % 4)
    rest = data[json_end:]
    out = bytearray()
    out += struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(encoded) + len(rest))
    out += struct.pack("<II", len(encoded), 0x4E4F534A)
    out += encoded
    out += rest
    path.write_bytes(out)


def build(output: Path) -> None:
    import bpy
    from mathutils import Vector

    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for collection in list(bpy.data.collections):
        if collection.name != "Collection":
            bpy.data.collections.remove(collection)

    root = bpy.context.scene.collection
    groups = {}
    for name in ["TERRACE", "BALUSTRADE", "HALL_BODY", "ROOFS", "EAVES_AND_BRACKETS", "SITE", "LIGHTS", "CAMERAS"]:
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
        return mat

    def procedural_surface(mat, base, dark, scale, detail=8, bump=0.0):
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        bsdf = next(n for n in nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = scale
        noise.inputs["Detail"].default_value = detail
        noise.inputs["Roughness"].default_value = 0.58
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.24
        ramp.color_ramp.elements[0].color = (*dark, 1)
        ramp.color_ramp.elements[1].position = 1.0
        ramp.color_ramp.elements[1].color = (*base, 1)
        links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        if bump:
            bump_node = nodes.new("ShaderNodeBump")
            bump_node.inputs["Strength"].default_value = bump
            bump_node.inputs["Distance"].default_value = 0.08
            links.new(noise.outputs["Fac"], bump_node.inputs["Height"])
            links.new(bump_node.outputs["Normal"], bsdf.inputs["Normal"])

    marble = material("slightly_warm_hanbaiyu_marble", (0.76, 0.74, 0.68), 0.88)
    marble_dark = material("marble_joint_shadow", (0.42, 0.41, 0.38), 0.9)
    vermilion = material("aged_vermilion_lacquered_wood", (0.48, 0.035, 0.018), 0.72)
    dark_red = material("deep_shadow_red_wood", (0.20, 0.012, 0.008), 0.78)
    blue_tile = material("deep_cobalt_blue_glazed_tile", (0.012, 0.060, 0.210), 0.34)
    tile_highlight = material("blue_tile_highlight_edges", (0.035, 0.145, 0.42), 0.28)
    gold = material("aged_gilded_roof_finial", (0.95, 0.62, 0.12), 0.38, 0.2)
    muted_gold = material("muted_gold_linework", (0.63, 0.42, 0.10), 0.55, 0.05)
    jade = material("painted_green_dougong", (0.03, 0.22, 0.12), 0.68)
    cyan = material("painted_cyan_beam_detail", (0.06, 0.28, 0.32), 0.68)
    ochre = material("painted_ochre_bracket_detail", (0.56, 0.28, 0.055), 0.7)
    black = material("black_lacquer_shadow_panels", (0.018, 0.015, 0.012), 0.62)
    paving = material("large_gray_stone_paving", (0.42, 0.42, 0.39), 0.86)
    procedural_surface(marble, (0.78, 0.76, 0.70), (0.52, 0.51, 0.47), 38, 12, 0.035)
    procedural_surface(vermilion, (0.52, 0.04, 0.02), (0.25, 0.015, 0.008), 24, 10, 0.025)
    procedural_surface(dark_red, (0.25, 0.018, 0.011), (0.09, 0.006, 0.004), 18, 8, 0.02)
    procedural_surface(blue_tile, (0.018, 0.085, 0.28), (0.003, 0.025, 0.105), 56, 12, 0.018)
    procedural_surface(tile_highlight, (0.055, 0.18, 0.48), (0.012, 0.06, 0.20), 64, 12, 0.014)
    procedural_surface(gold, (0.98, 0.68, 0.18), (0.46, 0.28, 0.055), 30, 8, 0.012)
    procedural_surface(paving, (0.47, 0.47, 0.43), (0.30, 0.30, 0.28), 34, 8, 0.025)

    def normals(obj):
        if obj.type == "MESH":
            obj.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
        return obj

    def smooth(obj):
        if obj.type == "MESH":
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.shade_smooth()
            obj.select_set(False)
        return obj

    def cube(name, loc, dims, mat, group, rot=(0, 0, 0), bevel=0.0):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
        obj = bpy.context.object
        obj.name = name
        obj.dimensions = dims
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(mat)
        if bevel:
            mod = obj.modifiers.new("small_bevel", "BEVEL")
            mod.width = bevel
            mod.segments = 2
        return link(normals(obj), group)

    def cyl(name, loc, radius, depth, mat, group, vertices=64, rot=(0, 0, 0), bevel=False):
        bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rot)
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(mat)
        if bevel:
            mod = obj.modifiers.new("rim_bevel", "BEVEL")
            mod.width = 0.04
            mod.segments = 2
        return link(normals(smooth(obj)), group)

    def cone(name, loc, r1, r2, depth, mat, group, vertices=160):
        bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=r1, radius2=r2, depth=depth, location=loc)
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(mat)
        return link(normals(obj), group)

    def torus(name, loc, major, minor, mat, group, rot=(0, 0, 0), scale=(1, 1, 1)):
        bpy.ops.mesh.primitive_torus_add(major_segments=192, minor_segments=12, major_radius=major, minor_radius=minor, location=loc, rotation=rot)
        obj = bpy.context.object
        obj.name = name
        obj.scale = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(mat)
        return link(normals(smooth(obj)), group)

    def sphere(name, loc, scale, mat, group):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1, location=loc)
        obj = bpy.context.object
        obj.name = name
        obj.scale = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(mat)
        return link(normals(smooth(obj)), group)

    def beam(name, start, end, radius, mat, group, vertices=12):
        av, bv = Vector(start), Vector(end)
        mid = (av + bv) / 2
        direction = bv - av
        bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=direction.length, location=mid)
        obj = bpy.context.object
        obj.name = name
        obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
        obj.data.materials.append(mat)
        return link(normals(smooth(obj)), group)

    def radial_cube(name, angle, radius, z, dims, mat, group, tilt=0.0, bevel=0.0):
        x, y = math.cos(angle) * radius, math.sin(angle) * radius
        return cube(name, (x, y, z), dims, mat, group, rot=(0, tilt, angle), bevel=bevel)

    def in_stair_gap(angle, half_width=0.17):
        for cardinal in [0, math.pi / 2, math.pi, math.pi * 1.5]:
            delta = abs((angle - cardinal + math.pi) % math.tau - math.pi)
            if delta < half_width:
                return True
        return False

    def aim(camera, target):
        camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()

    def roof_shell(name, base_z, radius, eave_radius, height, mat):
        # Curved-ish conical roof made from stacked frustums to avoid a toy cone silhouette.
        levels = [
            (eave_radius, radius * 0.86, base_z + 0.15, height * 0.24),
            (radius * 0.86, radius * 0.56, base_z + height * 0.34, height * 0.30),
            (radius * 0.56, radius * 0.22, base_z + height * 0.63, height * 0.28),
            (radius * 0.22, 0.42, base_z + height * 0.88, height * 0.18),
        ]
        for i, (r1, r2, z, d) in enumerate(levels):
            cone(f"{name}_curved_roof_frustum_{i}", (0, 0, z), r1, r2, d, mat, "ROOFS")
        torus(f"{name}_thick_blue_eave_lip", (0, 0, base_z - 0.02), eave_radius, 0.16, tile_highlight, "ROOFS")
        torus(f"{name}_upper_gold_bead", (0, 0, base_z + height * 0.93), 0.56, 0.065, gold, "ROOFS")
        for c in range(1, 8):
            f = c / 8
            ring = eave_radius * (1 - f) + 0.68 * f
            z = base_z + height * (0.08 + f * 0.82)
            torus(f"{name}_thin_shadow_tile_course_{c}", (0, 0, z - 0.015), ring, 0.010, blue_tile, "ROOFS")
            torus(f"{name}_raised_glaze_highlight_course_{c}", (0, 0, z + 0.006), ring * 0.992, 0.009, tile_highlight, "ROOFS")
        for i in range(72):
            a = math.tau * i / 72
            beam(
                f"{name}_radial_glazed_tile_rib_{i:02d}",
                (math.cos(a) * 0.52, math.sin(a) * 0.52, base_z + height * 0.98),
                (math.cos(a) * eave_radius * 0.985, math.sin(a) * eave_radius * 0.985, base_z + 0.05),
                0.020,
                tile_highlight if i % 3 else blue_tile,
                "ROOFS",
                8,
            )
        for ring, z in [(radius * 0.72, base_z + height * 0.30), (radius * 0.46, base_z + height * 0.58), (radius * 0.28, base_z + height * 0.78)]:
            torus(f"{name}_horizontal_tile_course_{z:.2f}", (0, 0, z), ring, 0.025, tile_highlight, "ROOFS")
        for row, (ring, z, tile_count) in enumerate([
            (eave_radius * 0.90, base_z + height * 0.14, 120),
            (radius * 0.74, base_z + height * 0.31, 108),
            (radius * 0.56, base_z + height * 0.48, 90),
            (radius * 0.38, base_z + height * 0.67, 72),
        ]):
            for i in range(tile_count):
                if i % 2:
                    continue
                a = math.tau * (i + row * 0.5) / tile_count
                radial_cube(f"{name}_individual_glazed_tile_{row}_{i:03d}", a, ring, z, (0.10, 0.24, 0.035), tile_highlight, "ROOFS", tilt=math.radians(12), bevel=0.006)

    def balustrade_ring(prefix, radius, z, posts, height):
        rail_segments = max(32, posts // 2)
        for j in range(rail_segments):
            a0 = math.tau * j / rail_segments
            a1 = math.tau * (j + 1) / rail_segments
            mid = (a0 + a1) / 2
            if in_stair_gap(mid):
                continue
            for label, rz, rr in [("lower", z + 0.22, 0.035), ("upper", z + height, 0.045)]:
                beam(
                    f"{prefix}_{label}_segmented_rail_{j:03d}",
                    (math.cos(a0) * radius, math.sin(a0) * radius, rz),
                    (math.cos(a1) * radius, math.sin(a1) * radius, rz),
                    rr,
                    marble,
                    "BALUSTRADE",
                    10,
                )
        for i in range(posts):
            a = math.tau * i / posts
            if in_stair_gap(a):
                continue
            x, y = math.cos(a) * radius, math.sin(a) * radius
            cube(f"{prefix}_carved_post_{i:03d}", (x, y, z + height / 2), (0.18, 0.18, height), marble, "BALUSTRADE", rot=(0, 0, a), bevel=0.035)
            if i % 3 == 0:
                sphere(f"{prefix}_post_cap_{i:03d}", (x, y, z + height + 0.12), (0.13, 0.13, 0.09), marble, "BALUSTRADE")
            if i % 6 == 0:
                beam(f"{prefix}_dragon_spout_{i:03d}", (math.cos(a) * (radius - 0.14), math.sin(a) * (radius - 0.14), z + 0.32), (math.cos(a) * (radius + 0.42), math.sin(a) * (radius + 0.42), z + 0.25), 0.035, marble_dark, "BALUSTRADE", 8)
            if i % 2 == 0:
                panel_angle = a + math.pi / posts
                radial_cube(f"{prefix}_openwork_stone_panel_{i:03d}", panel_angle, radius, z + height * 0.55, (0.34, 0.055, 0.34), marble, "BALUSTRADE", bevel=0.018)
                radial_cube(f"{prefix}_panel_inner_shadow_{i:03d}", panel_angle, radius * 1.002, z + height * 0.55, (0.20, 0.025, 0.20), marble_dark, "BALUSTRADE", bevel=0.008)

    def stair_stack(prefix, angle, r_outer, r_inner, z0, step_count, width, group="TERRACE"):
        forward = Vector((math.cos(angle), math.sin(angle), 0))
        right = Vector((-math.sin(angle), math.cos(angle), 0))
        depth = (r_outer - r_inner) / step_count
        rise = 0.080
        for i in range(step_count):
            r = r_outer - (i + 0.5) * depth
            pos = forward * r
            loc = (pos.x, pos.y, z0 + 0.05 + i * rise)
            cube(f"{prefix}_visible_riser_{i:02d}", (pos.x, pos.y, z0 + i * rise), (width, 0.045, rise), marble_dark, group, rot=(0, 0, angle + math.pi / 2), bevel=0.004)
            cube(f"{prefix}_white_marble_tread_{i:02d}", loc, (width, depth * 0.92, 0.09), marble, group, rot=(0, 0, angle + math.pi / 2), bevel=0.015)
            if i in (1, step_count - 2):
                for side in [-1, 1]:
                    p = pos + right * side * (width / 2 + 0.22)
                    cube(f"{prefix}_stair_guard_post_{i}_{side}", (p.x, p.y, z0 + 0.30 + i * rise), (0.16, 0.16, 0.60), marble, "BALUSTRADE", rot=(0, 0, angle), bevel=0.025)
        for side in [-1, 1]:
            for rail_z in [z0 + 0.40, z0 + step_count * rise + 0.32]:
                start = forward * (r_outer - depth * 0.35) + right * side * (width / 2 + 0.26)
                end = forward * (r_inner + depth * 0.35) + right * side * (width / 2 + 0.26)
                beam(f"{prefix}_side_stair_rail_{side}_{rail_z:.2f}", (start.x, start.y, rail_z), (end.x, end.y, rail_z + 0.18), 0.035, marble, "BALUSTRADE", 10)
        ramp_mid = forward * ((r_outer + r_inner) / 2)
        cube(f"{prefix}_carved_center_ramp", (ramp_mid.x, ramp_mid.y, z0 + 0.40), (width * 0.34, r_outer - r_inner, 0.055), marble, group, rot=(0, 0, angle + math.pi / 2), bevel=0.02)
        for j in range(5):
            relief = forward * (r_inner + (j + 1) * (r_outer - r_inner) / 6)
            cube(f"{prefix}_center_ramp_relief_{j}", (relief.x, relief.y, z0 + 0.45), (width * 0.22, 0.055, 0.035), marble_dark, group, rot=(0, 0, angle + math.pi / 2), bevel=0.01)

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene["target"] = "Qiniandian / Hall of Prayer for Good Harvests"
    scene["scope"] = "Exterior-only realistic procedural reconstruction."
    scene["truth_status"] = "Approximate, reference-informed; not survey or photogrammetry accurate."
    scene["reference_dimensions"] = "Hall commonly cited around 24.2 m diameter and 38 m tall; three-tier marble base and triple blue conical roof."
    scene.render.resolution_x = 2200
    scene.render.resolution_y = 1400
    scene.render.image_settings.file_format = "PNG"
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.eevee.taa_render_samples = 128
        if hasattr(scene.eevee, "use_gtao"):
            scene.eevee.use_gtao = True
            scene.eevee.gtao_distance = 4
            scene.eevee.gtao_factor = 1.2
    except Exception:
        scene.render.engine = "BLENDER_EEVEE"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.05

    cube("large_square_stone_courtyard_slab", (0, 0, -0.09), (58, 58, 0.18), paving, "SITE")
    for gx in range(-5, 6):
        cube(f"courtyard_paving_joint_x_{gx}", (gx * 5, 0, 0.012), (0.035, 55, 0.012), marble_dark, "SITE")
        cube(f"courtyard_paving_joint_y_{gx}", (0, gx * 5, 0.014), (55, 0.035, 0.012), marble_dark, "SITE")

    for radius, z, height, name in [(18.0, 0.25, 0.50, "lower"), (15.2, 0.95, 0.58, "middle"), (12.3, 1.73, 0.62, "upper")]:
        cyl(f"{name}_round_marble_platform", (0, 0, z), radius, height, marble, "TERRACE", 192, bevel=True)
        torus(f"{name}_dark_shadow_under_nosing", (0, 0, z + height / 2 + 0.02), radius - 0.15, 0.045, marble_dark, "TERRACE")
        torus(f"{name}_outer_molded_marble_edge", (0, 0, z + height / 2 + 0.12), radius, 0.075, marble, "TERRACE")
    for a in [0, math.pi / 2, math.pi, math.pi * 1.5]:
        stair_stack(f"lower_cardinal_{int(a * 100)}", a, 19.8, 15.6, 0.08, 9, 4.6)
        stair_stack(f"middle_cardinal_{int(a * 100)}", a, 16.7, 13.0, 0.78, 9, 4.1)
        stair_stack(f"upper_cardinal_{int(a * 100)}", a, 13.7, 10.3, 1.53, 9, 3.7)
    balustrade_ring("lower_platform", 17.7, 0.55, 96, 0.72)
    balustrade_ring("middle_platform", 14.9, 1.22, 84, 0.74)
    balustrade_ring("upper_platform", 12.0, 2.03, 72, 0.76)

    cyl("round_red_timber_hall_wall", (0, 0, 5.05), 8.65, 5.65, vermilion, "HALL_BODY", 160)
    cyl("dark_recessed_inner_shadow", (0, 0, 5.0), 8.10, 5.35, black, "HALL_BODY", 160)
    for i in range(24):
        a = math.tau * i / 24
        x, y = math.cos(a) * 8.95, math.sin(a) * 8.95
        cyl(f"outer_vermilion_column_{i:02d}", (x, y, 5.10), 0.22, 5.95, vermilion, "HALL_BODY", 24)
        cyl(f"outer_column_gold_base_{i:02d}", (x, y, 2.18), 0.28, 0.18, gold, "HALL_BODY", 24)
        cyl(f"outer_column_gold_cap_{i:02d}", (x, y, 8.05), 0.30, 0.20, gold, "HALL_BODY", 24)
    for ring_name, radius, count, z in [("middle_symbolic_column_ring", 5.4, 12, 5.0), ("inner_shadow_column_ring", 2.4, 12, 5.0)]:
        for i in range(count):
            a = math.tau * i / count + math.radians(7)
            cyl(f"{ring_name}_{i:02d}", (math.cos(a) * radius, math.sin(a) * radius, z), 0.14, 5.35, dark_red, "HALL_BODY", 18)
    for i in range(24):
        a = math.tau * i / 24
        radial_cube(f"dark_lattice_door_panel_{i:02d}", a, 8.72, 4.9, (1.0, 0.08, 2.9), black, "HALL_BODY", bevel=0.015)
        for j in [-0.40, -0.18, 0.0, 0.18, 0.40]:
            radial_cube(f"door_panel_gold_vertical_mullion_{i:02d}_{j}", a + j * 0.018, 8.79, 4.9, (0.040, 0.040, 2.78), muted_gold, "HALL_BODY")
        for z in [3.72, 4.35, 4.98, 5.61, 6.24]:
            radial_cube(f"door_panel_gold_horizontal_rail_{i:02d}_{z:.2f}", a, 8.80, z, (0.82, 0.035, 0.038), muted_gold, "HALL_BODY", bevel=0.004)
        for z in [4.05, 4.68, 5.31, 5.94]:
            radial_cube(f"door_panel_black_recess_shadow_line_{i:02d}_{z:.2f}", a, 8.815, z, (0.90, 0.020, 0.022), black, "HALL_BODY", bevel=0.003)
        for j in [-0.31, -0.09, 0.13, 0.35]:
            radial_cube(f"door_panel_red_lattice_stile_{i:02d}_{j}", a + j * 0.018, 8.825, 4.9, (0.030, 0.035, 2.62), dark_red, "HALL_BODY", bevel=0.003)
        radial_cube(f"red_recessed_wall_bay_frame_top_{i:02d}", a, 8.83, 6.53, (0.94, 0.055, 0.09), dark_red, "HALL_BODY", bevel=0.01)
        radial_cube(f"red_recessed_wall_bay_frame_bottom_{i:02d}", a, 8.83, 3.27, (0.94, 0.055, 0.09), dark_red, "HALL_BODY", bevel=0.01)
    for i in range(72):
        a = math.tau * i / 72
        radial_cube(f"painted_eave_dougong_block_outer_{i:02d}", a, 9.35, 8.22, (0.38, 0.38, 0.24), [jade, cyan, ochre][i % 3], "EAVES_AND_BRACKETS", bevel=0.025)
        radial_cube(f"painted_eave_cantilever_arm_{i:02d}", a, 9.70, 8.02, (0.18, 0.78, 0.15), cyan, "EAVES_AND_BRACKETS", bevel=0.018)
        radial_cube(f"gold_painted_dougong_face_{i:02d}", a, 9.56, 8.31, (0.18, 0.035, 0.085), muted_gold, "EAVES_AND_BRACKETS", bevel=0.006)
        if i % 2 == 0:
            radial_cube(f"second_layer_dougong_block_{i:02d}", a, 9.02, 7.86, (0.28, 0.32, 0.20), jade, "EAVES_AND_BRACKETS", bevel=0.018)
            radial_cube(f"under_eave_short_rafter_{i:02d}", a, 10.12, 7.72, (0.12, 1.05, 0.11), dark_red, "EAVES_AND_BRACKETS", tilt=math.radians(-4), bevel=0.01)
    for i in range(144):
        a = math.tau * i / 144
        radial_cube(f"lower_eave_dense_wooden_rafter_{i:03d}", a, 10.05, 8.08, (0.055, 0.88, 0.07), dark_red, "EAVES_AND_BRACKETS", tilt=math.radians(-5), bevel=0.004)
    torus("lower_round_beam_under_eave", (0, 0, 8.28), 8.95, 0.13, vermilion, "EAVES_AND_BRACKETS")
    torus("gold_painted_band_above_walls", (0, 0, 8.52), 8.72, 0.08, gold, "EAVES_AND_BRACKETS")
    for z, r, matline, label in [(7.72, 8.82, cyan, "cyan"), (7.92, 8.90, ochre, "ochre"), (8.12, 9.02, jade, "green")]:
        torus(f"{label}_painted_circular_eave_band_{z}", (0, 0, z), r, 0.045, matline, "EAVES_AND_BRACKETS")
    for i in range(96):
        a = math.tau * i / 96
        matline = [cyan, ochre, jade, muted_gold][i % 4]
        radial_cube(f"under_eave_painted_cloud_motif_{i:03d}", a, 9.18, 7.58, (0.20, 0.030, 0.070), matline, "EAVES_AND_BRACKETS", bevel=0.004)
        radial_cube(f"visible_fascia_painted_block_{i:03d}", a, 9.42, 8.42, (0.18, 0.032, 0.060), matline, "EAVES_AND_BRACKETS", bevel=0.004)
        if i % 2 == 0:
            radial_cube(f"under_eave_gold_pinstripe_{i:03d}", a, 9.00, 7.42, (0.11, 0.026, 0.045), muted_gold, "EAVES_AND_BRACKETS", bevel=0.003)

    roof_shell("lower_roof", 8.42, 8.2, 11.45, 5.1, blue_tile)
    roof_shell("middle_roof", 13.0, 5.8, 8.55, 4.2, blue_tile)
    roof_shell("upper_roof", 16.75, 3.4, 5.45, 3.45, blue_tile)
    cyl("golden_central_finial_stem", (0, 0, 21.7), 0.12, 2.0, gold, "ROOFS", 32)
    sphere("golden_finial_lower_ball", (0, 0, 20.9), (0.52, 0.52, 0.38), gold, "ROOFS")
    sphere("golden_finial_upper_ball", (0, 0, 22.8), (0.30, 0.30, 0.24), gold, "ROOFS")
    cone("golden_finial_tip", (0, 0, 23.55), 0.18, 0.02, 0.9, gold, "ROOFS", 48)

    for i in range(96):
        a = math.tau * i / 96
        radial_cube(f"lower_eave_blue_tile_end_{i:03d}", a, 11.45, 8.36, (0.13, 0.32, 0.16), tile_highlight, "ROOFS", bevel=0.012)
        if i % 2 == 0:
            radial_cube(f"lower_eave_gold_tile_nail_{i:03d}", a, 11.23, 8.52, (0.050, 0.030, 0.050), muted_gold, "ROOFS", bevel=0.006)
            radial_cube(f"lower_roof_small_glaze_chip_{i:03d}", a + math.radians(1.2), 10.88, 8.68, (0.060, 0.055, 0.030), tile_highlight, "ROOFS", tilt=math.radians(10), bevel=0.004)
    for i in range(72):
        a = math.tau * i / 72
        radial_cube(f"middle_eave_blue_tile_end_{i:03d}", a, 8.55, 12.94, (0.11, 0.28, 0.14), tile_highlight, "ROOFS", bevel=0.012)
        if i % 2 == 0:
            radial_cube(f"middle_eave_gold_tile_nail_{i:03d}", a, 8.38, 13.07, (0.044, 0.028, 0.044), muted_gold, "ROOFS", bevel=0.005)
    for i in range(48):
        a = math.tau * i / 48
        radial_cube(f"upper_eave_blue_tile_end_{i:03d}", a, 5.45, 16.70, (0.10, 0.24, 0.13), tile_highlight, "ROOFS", bevel=0.012)
        if i % 2 == 0:
            radial_cube(f"upper_eave_gold_tile_nail_{i:03d}", a, 5.31, 16.82, (0.040, 0.025, 0.040), muted_gold, "ROOFS", bevel=0.004)

    # Small front plaque and extra lintel detail. Unicode is intentional for the building inscription.
    cube("front_black_plaque_board", (0, -9.52, 7.03), (2.85, 0.14, 0.72), black, "HALL_BODY", bevel=0.04)
    bpy.ops.object.text_add(location=(0, -9.62, 7.03), rotation=(math.radians(90), 0, 0))
    plaque_text = bpy.context.object
    plaque_text.name = "front_plaque_qiniandian_text"
    font_path = Path("C:/Windows/Fonts/simhei.ttf")
    if font_path.exists():
        plaque_text.data.font = bpy.data.fonts.load(str(font_path))
    plaque_text.data.body = "\u7948\u5e74\u6bbf"
    plaque_text.data.align_x = "CENTER"
    plaque_text.data.align_y = "CENTER"
    plaque_text.data.size = 0.58
    plaque_text.data.extrude = 0.025
    plaque_text.data.materials.append(gold)
    link(plaque_text, "HALL_BODY")
    for i in range(7):
        x = -1.05 + i * 0.35
        cube(f"front_plaque_gold_border_pin_{i}", (x, -9.64, 7.43), (0.055, 0.035, 0.055), gold, "HALL_BODY", bevel=0.006)
    for i in range(9):
        x = -1.1 + i * 0.275
        cube(f"front_lintel_painted_gold_line_{i}", (x, -9.10, 6.78), (0.12, 0.035, 0.030), muted_gold, "HALL_BODY", bevel=0.004)

    bpy.ops.object.light_add(type="SUN", location=(-8, -14, 22))
    sun = bpy.context.object
    sun.name = "late_afternoon_sun"
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(42), 0, math.radians(-34))
    link(sun, "LIGHTS")
    bpy.ops.object.light_add(type="AREA", location=(0, -18, 15))
    fill = bpy.context.object
    fill.name = "large_soft_front_fill"
    fill.data.energy = 900
    fill.data.size = 18
    link(fill, "LIGHTS")
    bpy.ops.object.light_add(type="AREA", location=(0, -12, 7.5))
    plaque_fill = bpy.context.object
    plaque_fill.name = "soft_facade_detail_fill"
    plaque_fill.data.energy = 90
    plaque_fill.data.size = 4
    link(plaque_fill, "LIGHTS")

    def add_camera(name, loc, target, lens):
        bpy.ops.object.camera_add(location=loc)
        cam = bpy.context.object
        cam.name = name
        cam.data.lens = lens
        aim(cam, target)
        return link(cam, "CAMERAS")

    hero = add_camera("front_three_quarter_realistic_camera", (19, -31, 14), (0, 0, 8.8), 36)
    close = add_camera("roof_and_eave_detail_camera", (10, -17, 13.5), (0, -4, 12.2), 55)
    facade = add_camera("front_plaque_dougong_detail_camera", (0, -24, 7.35), (0, -9.2, 7.05), 58)
    top = add_camera("terrace_and_balustrade_camera", (0, -32, 11), (0, -1, 4.2), 45)
    scene.camera = hero
    world = bpy.data.worlds.new("qiniandian_clear_sky_world")
    world.color = (0.62, 0.70, 0.78)
    scene.world = world

    stage = output / "stage_00_qiniandian_exterior.blend"
    blend = output / "qiniandian_realistic.blend"
    glb = output / "qiniandian_realistic.glb"
    preview = output / "qiniandian_realistic_preview.png"
    close_preview = output / "qiniandian_roof_eave_detail.png"
    facade_preview = output / "qiniandian_front_facade_detail.png"
    terrace_preview = output / "qiniandian_terrace_detail.png"

    bpy.ops.wm.save_as_mainfile(filepath=str(stage))
    for camera, path in [(hero, preview), (close, close_preview), (facade, facade_preview), (top, terrace_preview)]:
        scene.camera = camera
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
    scene.camera = hero
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB", export_yup=True, export_apply=True)
    patch_glb_base_colors(glb)

    audit = {
        "target": "\u7948\u5e74\u6bbf / Hall of Prayer for Good Harvests",
        "scope": "exterior only",
        "truth_status": scene["truth_status"],
        "object_count": len(bpy.data.objects),
        "mesh_object_count": len([obj for obj in bpy.data.objects if obj.type == "MESH"]),
        "materials": len(bpy.data.materials),
        "modeled_features": [
            "three concentric marble terraces",
            "four cardinal stair sets with repeated steps",
            "circular balustrades with posts and water spouts",
            "24 outer columns plus symbolic inner column rings",
            "dark timber lattice doors and gold mullions",
            "procedural marble, lacquer, paving, gold and glazed-roof material noise/bump",
            "painted dougong blocks under eaves",
            "gold pinstripes and painted cloud motifs below the eaves",
            "second-layer dougong blocks and dense lower-eave rafters",
            "stone balustrade infill panels and center stair relief ramps",
            "individual raised glazed tile plates on each roof tier",
            "three stacked blue glazed roofs with radial tile ribs",
            "gold finial and bead courses",
        ],
        "references": [
            "https://whc.unesco.org/en/list/881/",
            "https://en.wikipedia.org/wiki/Temple_of_Heaven",
            "https://www.chinadaily.com.cn/a/201812/10/WS5c0e018ea310eff303290196.html",
            "https://www.travelchinaguide.com/attraction/beijing/temple-of-heaven/hall-of-prayer-for-good-harvests.htm",
        ],
        "deliverables": {
            "blend": str(blend),
            "glb": str(glb),
            "preview": str(preview),
            "roof_detail": str(close_preview),
            "facade_detail": str(facade_preview),
            "terrace_detail": str(terrace_preview),
            "stage": str(stage),
        },
    }
    (output / "scene_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    build(args.output.resolve())


if __name__ == "__main__":
    main()
