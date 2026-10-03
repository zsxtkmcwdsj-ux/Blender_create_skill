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
    values = sys.argv[sys.argv.index("--") + 1 :]
    return values[values.index(name) + 1] if name in values else default


OUT = Path(arg("--output", ".")).resolve()
RUN = Path(arg("--run", str(OUT.parent.parent / "runs" / "bucea_room218_shell"))).resolve()
OUT.mkdir(parents=True, exist_ok=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for collection in list(bpy.data.collections):
    if collection.name != "Collection":
        bpy.data.collections.remove(collection)

root = bpy.context.scene.collection
groups = {}
for name in ["SPACE_ZONE", "BOUNDARIES", "OPENINGS", "INTERFACES", "HARD_FINISH", "LIGHTS", "CAMERAS"]:
    collection = bpy.data.collections.new(name)
    root.children.link(collection)
    groups[name] = collection


def link(obj, group="BOUNDARIES"):
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    groups[group].objects.link(obj)
    return obj


def material(name, color, roughness=0.7, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(node for node in mat.node_tree.nodes if node.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


WALL = material("painted_plaster", (0.72, 0.68, 0.60), 0.84)
CEILING = material("ceiling_paint", (0.90, 0.89, 0.84), 0.92)
FLOOR = material("light_oak_floor", (0.34, 0.20, 0.11), 0.58)
BASEBOARD = material("baseboard_white", (0.72, 0.70, 0.64), 0.62)
DOOR = material("door_wood_finish", (0.40, 0.21, 0.09), 0.58)
FRAME = material("door_window_frame", (0.22, 0.24, 0.23), 0.42, 0.08)
GLASS = material("window_glass", (0.035, 0.18, 0.30), 0.32)
LIGHT_PANEL = material("ceiling_light_diffuser", (1.0, 0.82, 0.56), 0.24)


def cube(name, loc, dims, mat=WALL, group="BOUNDARIES", bevel=0.0, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new("small_edge_bevel", "BEVEL")
        mod.width, mod.segments = bevel, 2
    return link(obj, group)


def aim(camera, target):
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()


scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.length_unit = "METERS"
scene.render.resolution_x, scene.render.resolution_y = 1400, 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene["workflow"] = "BOT-informed research_to_blender_skill"
scene["space_class"] = "bot:Space / single student dormitory room"
scene["storey_context"] = "Daxing Campus Building 7 Floor 2, Room 218"
scene["source_plan"] = r"E:\app\condex_project\Test_to_3D\test0022.jpg"
scene["source_paper"] = r"C:\Users\Lenovo\Desktop\智能体人研究\阶段1：虚拟场景搭建\参考文献\建筑术语论文.pdf"
scene["paper_model"] = "BOT: Zone contains Space; Space contains or interfaces with Elements; adjacent zones share boundary; interfaces qualify connections"
scene["space_topology"] = "single continuous hollow shell with boolean door/window openings"
scene["truth_status"] = "hard-finish concept shell; dimensions inferred from plan proportions"
scene["no_furniture"] = True

wall = 0.18
width, depth, height = 3.6, 5.4, 3.0
door_w, door_h = 1.0, 2.2
window_w, window_h = 1.8, 1.4

# Space zone: one mesh with continuous wall runs and explicit door/window openings.
# The sections share the same outer perimeter, so the room is closed without Boolean n-gon fillbacks.
window_bottom, window_top = 0.95, 2.35
half_w, half_outer_w = width / 2, width / 2 + wall / 2
front_y0, front_y1 = -wall / 2, wall / 2
back_y0, back_y1 = depth - wall / 2, depth + wall / 2
vertices, faces = [], []


def shell_box(x0, x1, y0, y1, z0, z1):
    start = len(vertices)
    vertices.extend([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                     (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)])
    faces.extend([
        (start + 0, start + 1, start + 2, start + 3),
        (start + 4, start + 7, start + 6, start + 5),
        (start + 0, start + 4, start + 5, start + 1),
        (start + 1, start + 5, start + 6, start + 2),
        (start + 2, start + 6, start + 7, start + 3),
        (start + 4, start + 0, start + 3, start + 7),
    ])


# Side walls and front/back wall sections are all part of this one mesh object.
shell_box(-half_outer_w, -half_w, 0, depth, 0, height)
shell_box(half_w, half_outer_w, 0, depth, 0, height)
shell_box(-half_outer_w, -door_w / 2, front_y0, front_y1, 0, height)
shell_box(door_w / 2, half_outer_w, front_y0, front_y1, 0, height)
shell_box(-door_w / 2, door_w / 2, front_y0, front_y1, door_h, height)
shell_box(-half_outer_w, -window_w / 2, back_y0, back_y1, 0, height)
shell_box(window_w / 2, half_outer_w, back_y0, back_y1, 0, height)
shell_box(-window_w / 2, window_w / 2, back_y0, back_y1, 0, window_bottom)
shell_box(-window_w / 2, window_w / 2, back_y0, back_y1, window_top, height)

mesh = bpy.data.meshes.new("room_shell_envelope_mesh")
mesh.from_pydata(vertices, [], faces)
mesh.update()
shell = bpy.data.objects.new("room_shell_envelope", mesh)
groups["SPACE_ZONE"].objects.link(shell)
shell.data.materials.append(WALL)

# Interior finish layers sit on the continuous shell surfaces.
cube("room_floor_slab", (0, depth / 2, 0.015), (width, depth, 0.03), FLOOR, "HARD_FINISH")
cube("room_ceiling_slab", (0, depth / 2, height - 0.015), (width, depth, 0.03), CEILING, "HARD_FINISH")

front_side_w = (width - door_w) / 2

# Door interface: threshold, jambs, head trim and a real leaf placed open into the room.
cube("door_threshold", (0, -0.05, 0.04), (door_w + 0.12, 0.32, 0.08), FRAME, "INTERFACES", 0.02)
cube("door_jamb_left", (-door_w / 2, 0.0, door_h / 2), (0.08, wall + 0.10, door_h), FRAME, "OPENINGS", 0.015)
cube("door_jamb_right", (door_w / 2, 0.0, door_h / 2), (0.08, wall + 0.10, door_h), FRAME, "OPENINGS", 0.015)
cube("door_head_trim", (0, 0.0, door_h), (door_w + 0.08, wall + 0.10, 0.08), FRAME, "OPENINGS", 0.015)
cube("door_leaf_open", (-0.42, 0.42, door_h / 2), (0.86, 0.06, door_h), DOOR, "OPENINGS", 0.02, (0, 0, math.radians(90)))

# Window interface: glazing, frame, sill and head remain part of the exterior boundary.
cube("window_glass", (0, depth - 0.01, (window_bottom + window_top) / 2), (window_w, 0.05, window_h), GLASS, "OPENINGS")
cube("window_frame_left", (-window_w / 2, depth, (window_bottom + window_top) / 2), (0.08, wall + 0.10, window_h + 0.14), FRAME, "OPENINGS", 0.015)
cube("window_frame_right", (window_w / 2, depth, (window_bottom + window_top) / 2), (0.08, wall + 0.10, window_h + 0.14), FRAME, "OPENINGS", 0.015)
cube("window_sill", (0, depth, window_bottom), (window_w + 0.16, wall + 0.14, 0.10), FRAME, "INTERFACES", 0.015)
cube("window_head", (0, depth, window_top), (window_w + 0.16, wall + 0.10, 0.10), FRAME, "INTERFACES", 0.015)
cube("window_mullion", (0, depth, (window_bottom + window_top) / 2), (0.06, 0.10, window_h), FRAME, "OPENINGS")

# Basic interior hard finish: continuous skirting follows the actual wall lines.
trim_h, trim_t = 0.10, 0.05
cube("baseboard_left", (-width / 2 + wall / 2, depth / 2, trim_h / 2), (trim_t, depth, trim_h), BASEBOARD, "HARD_FINISH", 0.008)
cube("baseboard_right", (width / 2 - wall / 2, depth / 2, trim_h / 2), (trim_t, depth, trim_h), BASEBOARD, "HARD_FINISH", 0.008)
cube("baseboard_back", (0, depth - wall / 2, trim_h / 2), (width, trim_t, trim_h), BASEBOARD, "HARD_FINISH", 0.008)
inner_side_half = width / 2 - wall / 2
front_trim_w = inner_side_half - door_w / 2
front_trim_x = (inner_side_half + door_w / 2) / 2
cube("baseboard_front_left", (-front_trim_x, wall / 2, trim_h / 2), (front_trim_w, trim_t, trim_h), BASEBOARD, "HARD_FINISH", 0.008)
cube("baseboard_front_right", (front_trim_x, wall / 2, trim_h / 2), (front_trim_w, trim_t, trim_h), BASEBOARD, "HARD_FINISH", 0.008)

# Simple ceiling light fixture; it is architectural finish, not furniture.
cube("ceiling_light_panel", (0, depth * 0.46, height - 0.105), (1.25, 0.32, 0.05), LIGHT_PANEL, "HARD_FINISH", 0.015)

# Warm ceiling light plus interior fill for a readable interior preview.
for loc, energy, size, color in [
    ((0, depth * 0.46, height - 0.28), 900, 1.8, (1.0, 0.78, 0.56)),
    ((1.8, 1.0, height - 0.42), 700, 2.5, (1.0, 0.90, 0.76)),
    ((0, depth * 0.42, 1.75), 220, 3.0, (1.0, 0.92, 0.82)),
    ((0, -3.4, 3.8), 900, 3.5, (0.82, 0.90, 1.0)),
]:
    bpy.ops.object.light_add(type="AREA", location=loc)
    light = bpy.context.object
    light.data.energy, light.data.size, light.data.color = energy, size, color
    aim(light, (0, 2.4, 1.2) if loc[2] > 2.0 else (0, 2.4, 2.9))
    link(light, "LIGHTS")

bpy.ops.object.camera_add(location=(4.8, -5.8, 3.4))
delivery_camera = bpy.context.object
delivery_camera.name = "camera_minimal_room_shell"
delivery_camera.data.lens = 40
aim(delivery_camera, (0, 0.65, 1.15))
link(delivery_camera, "CAMERAS")

scene.world = bpy.data.worlds.new("room_soft_world")
scene.world.color = (0.08, 0.09, 0.10)
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    scene.render.engine = "BLENDER_EEVEE"
scene.view_settings.look = "AgX - Medium High Contrast"

blend_path = OUT / "bucea_room218_shell.blend"
glb_path = OUT / "bucea_room218_shell.glb"
preview_path = OUT / "bucea_room218_shell_preview.png"
window_preview_path = OUT / "bucea_room218_shell_window_preview.png"

scene.camera = delivery_camera
scene.render.filepath = str(preview_path)
bpy.ops.render.render(write_still=True)

# A second view verifies the opposite opening without adding another persistent camera.
delivery_camera.location = (1.15, 0.95, 1.55)
delivery_camera.data.lens = 32
aim(delivery_camera, (0, 3.45, 1.35))
scene.render.filepath = str(window_preview_path)
bpy.ops.render.render(write_still=True)

# Keep the delivered file opened at the doorway overview.
delivery_camera.location = (4.8, -5.8, 3.4)
delivery_camera.data.lens = 40
aim(delivery_camera, (0, 0.65, 1.15))
scene.render.filepath = str(preview_path)

# Cameras are hidden from the viewport; lights remain enabled for rendered viewport mode.
groups["CAMERAS"].hide_viewport = True
groups["LIGHTS"].hide_viewport = False
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
bpy.ops.export_scene.gltf(filepath=str(glb_path), export_format="GLB", export_yup=True, export_apply=True)

required = [
    "room_shell_envelope", "room_floor_slab", "room_ceiling_slab", "door_jamb_left", "door_jamb_right", "door_head_trim",
    "door_leaf_open", "window_glass", "window_sill", "window_head",
]
audit = {
    "target": scene["storey_context"],
    "space_type": scene["space_class"],
    "truth_status": scene["truth_status"],
    "furniture_present": any(obj.name.lower().find("bed") >= 0 or obj.name.lower().find("desk") >= 0 for obj in bpy.data.objects),
    "inferred_dimensions_m": {"width": width, "depth": depth, "height": height, "wall": wall, "door_width": door_w, "door_height": door_h, "window_width": window_w, "window_height": window_h},
    "space_contract": {"continuous_shell": True, "shell_object": "room_shell_envelope", "floor": True, "walls": ["continuous left/right/front/back shell", "wall above door retained", "wall around window retained"], "ceiling": True, "openings": ["door to corridor", "exterior window"], "interfaces": ["door threshold/frame/head", "window sill/frame/head"], "connections": ["room -> corridor by door"]},
    "missing_required_objects": [name for name in required if bpy.data.objects.get(name) is None],
    "objects_total": len(bpy.data.objects),
    "outputs": [blend_path.name, glb_path.name, preview_path.name, window_preview_path.name],
}
(OUT / "scene_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"blend": str(blend_path), "glb": str(glb_path), "preview": str(preview_path)}, ensure_ascii=False))
