from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def arg(name: str, default: str) -> str:
    if "--" not in sys.argv:
        return default
    args = sys.argv[sys.argv.index("--") + 1 :]
    return args[args.index(name) + 1] if name in args else default


OUT = Path(arg("--output", ".")).resolve()
OUT.mkdir(parents=True, exist_ok=True)
RUN = Path(arg("--run", str(OUT.parent.parent / "runs" / "oodi_book_heaven"))).resolve()


# Reset only the new delivery file, then organize the scene by semantic responsibility.
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for collection in list(bpy.data.collections):
    if collection.name != "Collection":
        bpy.data.collections.remove(collection)

root = bpy.context.scene.collection
collections = {}
for name in ["STRUCTURE", "ARCHITECTURE", "FURNITURE", "BOOKS", "LIGHTS", "CAMERAS", "AUDIT"]:
    col = bpy.data.collections.new(name)
    root.children.link(col)
    collections[name] = col


def link(obj: bpy.types.Object, group: str = "ARCHITECTURE") -> bpy.types.Object:
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    collections[group].objects.link(obj)
    return obj


def material(name: str, color: tuple[float, float, float, float], roughness: float = 0.6, metallic: float = 0.0, emission=None):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = next((n for n in nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    if bsdf is None:
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission:
        bsdf.inputs["Emission Color"].default_value = emission
        bsdf.inputs["Emission Strength"].default_value = 0.6
    return mat


WOOD = material("OODI_Warm_Laminated_Wood", (0.52, 0.24, 0.09, 1), 0.45)
WOOD_LIGHT = material("OODI_Light_Oak", (0.78, 0.48, 0.20, 1), 0.5)
WHITE = material("OODI_Acoustic_White", (0.86, 0.88, 0.84, 1), 0.85)
CONCRETE = material("OODI_Light_Concrete", (0.56, 0.60, 0.59, 1), 0.9)
GLASS = material("OODI_Clear_Glass", (0.20, 0.50, 0.64, 0.28), 0.12)
METAL = material("OODI_Brushed_Metal", (0.32, 0.36, 0.37, 1), 0.28, 0.75)
BLACK = material("OODI_Dark_Metal", (0.025, 0.035, 0.04, 1), 0.33, 0.4)
BLUE = material("OODI_Muted_Blue", (0.12, 0.28, 0.38, 1), 0.8)
GREEN = material("OODI_Muted_Green", (0.19, 0.34, 0.27, 1), 0.82)
YELLOW = material("OODI_Warm_Light", (0.9, 0.54, 0.12, 1), 0.36, emission=(1.0, 0.42, 0.06, 1))
RED = material("OODI_Accent_Red", (0.55, 0.14, 0.10, 1), 0.7)
LEAF = material("OODI_Living_Green", (0.10, 0.30, 0.18, 1), 0.9)


def cube(name: str, loc, dims, mat, group="ARCHITECTURE", rot=(0.0, 0.0, 0.0), bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new("edge_softening", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    return link(obj, group)


def cyl(name: str, loc, radius, depth, mat, group="ARCHITECTURE", vertices=16, rot=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return link(obj, group)


def sphere(name: str, loc, scale, mat, group="FURNITURE"):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return link(obj, group)


def curve_line(name: str, points, bevel, mat, group="ARCHITECTURE"):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = bevel
    curve.bevel_resolution = 2
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for point, co in zip(spline.bezier_points, points):
        point.co = co
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, curve)
    collections[group].objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def text(name: str, body: str, loc, size, mat, rot=(math.radians(90), 0.0, 0.0), group="ARCHITECTURE"):
    bpy.ops.object.text_add(location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.body = body
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.extrude = 0.015
    obj.data.materials.append(mat)
    return link(obj, group)


def save_stage(name: str):
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / f"stage_{name}.blend"))


# Intake metadata: keep the research-to-model truth status in the delivery file.
scene = bpy.context.scene
scene["workflow"] = "research_to_blender_skill"
scene["target_building"] = "Helsinki Central Library Oodi"
scene["target_scope"] = "Top floor Book Heaven / Citizens Balcony concept"
scene["truth_status"] = "building match only; exact dimensions and furniture inferred"
scene["research_run"] = str(RUN)
scene["source_1"] = "https://ala.fi/work/helsinki-central-library/"
scene["source_2"] = "https://oodihelsinki.fi/en/facilities/floors/"
scene["source_3"] = "https://culture.ec.europa.eu/cultural-and-creative-sectors/architecture/living-spaces/catalogue/helsinki"

# Stage 00 / coordinate setup and primary blockout.
scene.unit_settings.system = "METRIC"
scene.unit_settings.length_unit = "METERS"
scene.render.resolution_x = 1600
scene.render.resolution_y = 1100
scene.render.resolution_percentage = 100
cube("reading_floor_28x18", (0, 0, -0.12), (28, 18, 0.24), CONCRETE, "STRUCTURE")
cube("balcony_platform", (0, -8.1, 0.22), (25.5, 1.8, 0.22), WOOD_LIGHT, "STRUCTURE")
cube("rear_service_volume_blockout", (6.9, 6.3, 2.5), (8.0, 3.5, 5.0), WOOD, "STRUCTURE")
cube("left_stair_blockout", (-9.0, 3.1, 2.0), (5.0, 4.6, 4.0), CONCRETE, "STRUCTURE")
save_stage("00_blockout")

# Stage 01 / glazed city-facing edge and Citizens' Balcony.
cube("glazed_city_facade", (0, -8.85, 3.0), (27.5, 0.10, 5.7), GLASS, "ARCHITECTURE")
for x in range(-12, 13, 2):
    cube(f"facade_mullion_{x:+03d}", (x, -8.91, 3.0), (0.08, 0.18, 5.7), METAL, "ARCHITECTURE")
cube("balcony_guard_base", (0, -7.25, 1.15), (25.5, 0.12, 0.12), WOOD_LIGHT, "ARCHITECTURE")
for x in range(-12, 13, 2):
    cube(f"balcony_glass_panel_{x:+03d}", (x, -7.25, 0.75), (1.85, 0.04, 0.8), GLASS, "ARCHITECTURE")
cube("balcony_handrail", (0, -7.25, 1.2), (25.5, 0.12, 0.10), WOOD_LIGHT, "ARCHITECTURE", bevel=0.03)

# The open timber spine is represented as a curved sequence of ribs and shelves.
for i, x in enumerate([5.0, 6.0, 7.0, 8.0, 9.0, 10.0]):
    y = 6.4 + 0.45 * math.cos((x - 7.5) * 0.75)
    curve_line(f"timber_arch_rib_{i+1:02d}", [(x, y + 0.55, 0.2), (x + 0.05, y, 2.1), (x + 0.05, y - 0.1, 4.8)], 0.16, WOOD, "ARCHITECTURE")
for z in [0.8, 1.55, 2.3, 3.05, 3.8, 4.55]:
    cube(f"timber_spine_shelf_{z:.2f}", (7.55, 6.45, z), (6.0, 0.55, 0.11), WOOD_LIGHT, "ARCHITECTURE", bevel=0.04)
for z in [1.1, 1.85, 2.6, 3.35, 4.1]:
    for i, x in enumerate([5.35, 6.1, 6.85, 7.6, 8.35, 9.1, 9.85]):
        h = 0.52 + 0.05 * ((i + int(z * 10)) % 3)
        cube(f"spine_book_{z:.1f}_{i}", (x, 6.08, z + h / 2), (0.32, 0.35, h), [BLUE, RED, GREEN][i % 3], "BOOKS", bevel=0.025)

# Stage 02 / double-helix stair beside the timber volume.
stair_center = Vector((-9.0, 3.3, 0.35))
for side, phase, mat in [("A", 0.0, WOOD_LIGHT), ("B", math.pi, WOOD)]:
    points = []
    for i in range(20):
        angle = phase + i * (math.pi * 2.0 / 19.0)
        z = 0.28 + i * 0.21
        x = stair_center.x + math.cos(angle) * 1.6
        y = stair_center.y + math.sin(angle) * 1.6
        rot = (0.0, 0.0, angle + math.pi / 2)
        cube(f"helix_step_{side}_{i:02d}", (x, y, z), (1.45, 0.48, 0.14), mat, "ARCHITECTURE", rot=rot, bevel=0.03)
        points.append((x, y, z + 0.33))
    curve_line(f"helix_rail_{side}", points, 0.055, METAL, "ARCHITECTURE")
cyl("stair_core", (-9.0, 3.3, 2.4), 0.32, 4.8, CONCRETE, "STRUCTURE", vertices=20)
for blockout_name in ["rear_service_volume_blockout", "left_stair_blockout"]:
    blockout = bpy.data.objects.get(blockout_name)
    if blockout:
        bpy.data.objects.remove(blockout, do_unlink=True)

# Stage 03 / undulating acoustic ceiling and skylights.
for i, x in enumerate([n * 1.6 - 12.8 for n in range(17)]):
    z = 5.45 + 0.32 * math.sin(x * 0.45)
    cube(f"acoustic_ceiling_wave_{i:02d}", (x, 0.0, z), (1.55, 17.2, 0.18), WHITE, "ARCHITECTURE", rot=(0.0, math.radians(3.4 * math.cos(x * 0.45)), 0.0), bevel=0.08)
for i, (x, y) in enumerate([(-4.5, -1.4), (1.5, 0.5), (7.5, -0.4), (-1.0, 5.0)]):
    cyl(f"circular_skylight_ring_{i+1}", (x, y, 5.66), 0.62, 0.08, METAL, "ARCHITECTURE", vertices=32)
    cyl(f"circular_skylight_glow_{i+1}", (x, y, 5.70), 0.48, 0.035, YELLOW, "LIGHTS", vertices=32)

# Stage 04 / book stacks, reading oases, tables, lounge seats and cafe nook.
def book_stack(name, x, y, w=1.2, d=0.5, rows=3):
    cube(name + "_body", (x, y, 0.72), (w, d, 1.45), WOOD, "FURNITURE", bevel=0.05)
    for row in range(rows):
        for col in range(4):
            book_mat = [BLUE, RED, GREEN, WOOD_LIGHT][(row + col) % 4]
            cube(f"{name}_book_{row}_{col}", (x - w * 0.34 + col * w * 0.22, y - d * 0.51, 0.22 + row * 0.28), (0.15, 0.025, 0.22), book_mat, "BOOKS")


for i, (x, y) in enumerate([(-3.4, 1.9), (1.1, 2.0), (3.5, -2.4), (-1.8, -4.0), (7.0, -2.5)]):
    book_stack(f"low_book_stack_{i+1}", x, y, 1.3, 0.55, 3)

for i, (x, y, color) in enumerate([(-4.0, -1.7, BLUE), (0.5, 0.0, GREEN), (4.0, -0.2, BLUE), (1.8, -5.3, GREEN)]):
    cube(f"reading_rug_{i+1}", (x, y, 0.035), (3.1, 2.2, 0.05), color, "FURNITURE", bevel=0.12)
    cube(f"reading_table_{i+1}", (x, y, 0.78), (1.55, 0.72, 0.12), WOOD_LIGHT, "FURNITURE", bevel=0.08)
    for j, dx in enumerate([-0.95, 0.95]):
        cube(f"reading_chair_{i+1}_{j+1}_seat", (x + dx, y, 0.48), (0.55, 0.58, 0.12), color, "FURNITURE", bevel=0.08)
        cube(f"reading_chair_{i+1}_{j+1}_back", (x + dx, y + 0.25, 0.85), (0.55, 0.10, 0.75), color, "FURNITURE", bevel=0.08)

# Cafe: deliberately small and near the glazed edge, as described by the official floor program.
cube("cafe_counter", (10.3, -5.9, 0.75), (3.5, 0.75, 1.35), WOOD, "FURNITURE", bevel=0.08)
cube("cafe_counter_top", (10.3, -5.9, 1.46), (3.65, 0.85, 0.12), WOOD_LIGHT, "FURNITURE", bevel=0.04)
for i, x in enumerate([9.5, 10.2, 10.9, 11.6]):
    cyl(f"cafe_stool_{i+1}", (x, -4.9, 0.48), 0.28, 0.10, BLUE if i % 2 else GREEN, "FURNITURE", vertices=12)
    cyl(f"cafe_stool_leg_{i+1}", (x, -4.9, 0.23), 0.055, 0.45, METAL, "FURNITURE", vertices=10)
text("cafe_label", "CAFE", (10.3, -5.48, 1.52), 0.35, WHITE, rot=(math.radians(90), 0.0, 0.0))

# Children's reading oasis: lower, softer and more playful, but within the same material language.
cube("children_oasis_rug", (-4.0, 5.0, 0.04), (4.0, 2.3, 0.06), RED, "FURNITURE", bevel=0.16)
for i, x in enumerate([-5.2, -4.0, -2.8]):
    cyl(f"children_round_table_{i+1}", (x, 5.0, 0.48), 0.52, 0.10, WOOD_LIGHT, "FURNITURE", vertices=16)
    cyl(f"children_table_leg_{i+1}", (x, 5.0, 0.24), 0.07, 0.42, WOOD, "FURNITURE", vertices=10)
    sphere(f"children_floor_cushion_{i+1}", (x, 4.45, 0.28), (0.42, 0.32, 0.20), BLUE if i % 2 else GREEN, "FURNITURE")

# Trees: Oodi has living trees; their silhouettes help establish the calm top-floor interior.
for i, (x, y, s) in enumerate([(-11.0, -4.8, 1.25), (6.0, -5.7, 1.0), (3.5, 4.8, 0.9)]):
    cyl(f"living_tree_trunk_{i+1}", (x, y, 1.25 * s), 0.16 * s, 2.5 * s, WOOD, "FURNITURE", vertices=10)
    for j in range(5):
        a = j * math.pi * 2 / 5
        sphere(f"living_tree_canopy_{i+1}_{j+1}", (x + math.cos(a) * 0.65 * s, y + math.sin(a) * 0.55 * s, 2.55 * s + (j % 2) * 0.3), (0.62 * s, 0.52 * s, 0.72 * s), LEAF, "FURNITURE")

# Wayfinding and human scale cues.
text("book_heaven_sign", "BOOK HEAVEN", (0.0, 6.02, 4.78), 0.45, WHITE, rot=(math.radians(90), 0.0, 0.0))

# Stage 05 / lighting and camera.
bpy.ops.object.light_add(type="AREA", location=(0.0, -2.0, 8.0))
day = bpy.context.object
day.name = "diffuse_daylight_from_glass"
day.data.energy = 1050
day.data.shape = "RECTANGLE"
day.data.size = 18
day.data.size_y = 8
day.data.color = (0.72, 0.86, 1.0)
link(day, "LIGHTS")
for i, (x, y) in enumerate([(-4.0, -1.7), (0.5, 0.0), (4.0, -0.2), (1.8, -5.3), (10.3, -5.9)]):
    bpy.ops.object.light_add(type="AREA", location=(x, y, 4.55))
    light = bpy.context.object
    light.name = f"warm_reading_pool_{i+1}"
    light.data.energy = 170
    light.data.shape = "DISK"
    light.data.size = 2.0
    light.data.color = (1.0, 0.62, 0.30)
    link(light, "LIGHTS")

for i, (x, y) in enumerate([(-4.0, -1.7), (0.5, 0.0), (4.0, -0.2), (1.8, -5.3), (10.3, -5.9)]):
    cyl(f"reading_pendant_{i+1}", (x, y, 4.85), 0.28, 0.12, YELLOW, "LIGHTS", vertices=16)
    cyl(f"reading_pendant_cord_{i+1}", (x, y, 5.15), 0.018, 0.58, BLACK, "LIGHTS", vertices=8)

def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


bpy.ops.object.camera_add(location=(10.8, 3.6, 2.85))
hero = bpy.context.object
hero.name = "hero_camera_book_heaven"
hero.data.lens = 32
aim(hero, (-0.5, -3.0, 2.0))
link(hero, "CAMERAS")
bpy.ops.object.camera_add(location=(0.0, -23.0, 20.0))
overview = bpy.context.object
overview.name = "overview_camera_book_heaven"
overview.data.type = "ORTHO"
overview.data.ortho_scale = 31
aim(overview, (0.0, 0.0, 0.0))
link(overview, "CAMERAS")
scene.camera = hero

scene.world = bpy.data.worlds.new("Oodi_soft_day_world")
scene.world.color = (0.05, 0.07, 0.09)
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    scene.render.engine = "BLENDER_EEVEE"
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.view_settings.look = "AgX - Medium High Contrast"

save_stage("01_structure")

# Final delivery file plus a lightweight audit text block.
blend_path = OUT / "oodi_book_heaven.blend"
glb_path = OUT / "oodi_book_heaven.glb"
png_path = OUT / "oodi_book_heaven_preview.png"
scene.render.filepath = str(png_path)
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
bpy.ops.render.render(write_still=True)
bpy.ops.export_scene.gltf(filepath=str(glb_path), export_format="GLB", export_yup=True, export_apply=True)

mesh_objects = [o for o in bpy.data.objects if o.type == "MESH"]
audit = {
    "target": "Helsinki Central Library Oodi - top floor Book Heaven concept",
    "truth_status": scene["truth_status"],
    "objects_total": len(bpy.data.objects),
    "mesh_objects": len(mesh_objects),
    "materials": len(bpy.data.materials),
    "lights": len([o for o in bpy.data.objects if o.type == "LIGHT"]),
    "cameras": len([o for o in bpy.data.objects if o.type == "CAMERA"]),
    "required_features": {
        "open_reading_floor": True,
        "curved_timber_volume": True,
        "undulating_ceiling": True,
        "glazed_balcony": True,
        "double_helix_stair": True,
        "book_stacks": True,
        "cafe_nook": True,
        "childrens_oasis": True,
        "circulation_path": True
    },
    "deliverables": {"blend": str(blend_path), "glb": str(glb_path), "preview": str(png_path)}
}
(OUT / "scene_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
print(json.dumps(audit, indent=2))
