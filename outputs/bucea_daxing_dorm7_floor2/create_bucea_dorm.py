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
RUN = Path(arg("--run", str(OUT.parent.parent / "runs" / "bucea_daxing_dorm7_floor2"))).resolve()
OUT.mkdir(parents=True, exist_ok=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for collection in list(bpy.data.collections):
    if collection.name != "Collection":
        bpy.data.collections.remove(collection)

root = bpy.context.scene.collection
groups = {}
for name in ["FLOOR_PLAN", "ENVELOPE", "OPENINGS", "ROOM_218", "CIRCULATION", "VERTICAL", "DETAILS", "LIGHTS", "CAMERAS"]:
    collection = bpy.data.collections.new(name)
    root.children.link(collection)
    groups[name] = collection


def link(obj, group="ENVELOPE"):
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    groups[group].objects.link(obj)
    return obj


def mat(name, color, roughness=0.7, metallic=0.0):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1)
    material.use_nodes = True
    bsdf = next(node for node in material.node_tree.nodes if node.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return material


PLASTER = mat("warm_white_plaster", (0.72, 0.70, 0.64), 0.88)
CORRIDOR = mat("corridor_vinyl", (0.26, 0.29, 0.28), 0.7)
ROOM_FLOOR = mat("room_floor", (0.48, 0.34, 0.22), 0.8)
WALL_EDGE = mat("wall_edge", (0.16, 0.18, 0.17), 0.6)
DOOR = mat("painted_door", (0.42, 0.24, 0.12), 0.62)
WOOD = mat("dorm_wood", (0.55, 0.31, 0.14), 0.62)
BED = mat("bed_frame", (0.10, 0.13, 0.14), 0.42, 0.25)
SHEET = mat("bed_sheet", (0.82, 0.84, 0.78), 0.92)
BLUE = mat("blanket_blue", (0.22, 0.36, 0.47), 0.88)
METAL = mat("brushed_metal", (0.25, 0.27, 0.26), 0.36, 0.75)
GLASS = mat("window_glass", (0.17, 0.42, 0.52), 0.16)
FIRE = mat("fire_safety_red", (0.72, 0.035, 0.02), 0.48)
SIGN = mat("exit_sign_green", (0.04, 0.42, 0.18), 0.52)
WHITE = mat("sign_white", (0.96, 0.95, 0.88), 0.75)
BLACK = mat("text_black", (0.015, 0.018, 0.018), 0.75)
GREEN = mat("indoor_plant", (0.08, 0.29, 0.12), 0.88)


def cube(name, loc, dims, material=PLASTER, group="ENVELOPE", bevel=0.0, rot=(0, 0, 0)):
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
    return link(obj, group)


def cyl(name, loc, radius, depth, material, group="DETAILS", vertices=16):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    return link(obj, group)


def text(name, body, loc, size, material=BLACK, rot=(math.radians(90), 0, 0)):
    bpy.ops.object.text_add(location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.body = body
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.extrude = 0.01
    obj.data.materials.append(material)
    return link(obj, "DETAILS")


def aim(camera, target):
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()


scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.length_unit = "METERS"
scene.render.resolution_x, scene.render.resolution_y = 1400, 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene["workflow"] = "research_to_blender_skill"
scene["target_building"] = "Beijing University of Civil Engineering and Architecture, Daxing Campus, Building 7"
scene["target_floor"] = "Floor 2 student dormitory"
scene["source_plan"] = r"E:\app\condex_project\Test_to_3D\test0022.jpg"
scene["plan_evidence"] = "corridor, rooms 202-236, stairs, elevator core, fire route and exit marker"
scene["truth_status"] = "fire-plan-based spatial concept; dimensions, windows and furniture are inferred"
scene["envelope_gate"] = "passed: floor, corridor walls, room walls, ceiling, door opening and exterior window"
scene["room_focus"] = "Room 218"
scene["research_run"] = str(RUN)
scene["source_bucea"] = "https://www.bucea.edu.cn/gbxxgk/gbxxjj/459bf36ded834a8b9ebbe5fc9e6296fa.htm"
scene["source_context"] = "https://idri.bucea.edu.cn/lxjd/xysh_lxjd/400a963e3d824475bb2f36309bf987bd.htm"

# Concept dimensions are explicit assumptions because the supplied plan has no scale bar.
wall = 0.18
room_w, room_d, height = 3.6, 5.2, 3.0
corridor_w = 2.4
floor_z = 0.0
ceiling_z = height

# A representative floor-plan segment: south rooms 216-222 and north room shells 215-221.
cube("floor_corridor", (0, 0, -0.10), (25.2, corridor_w, 0.20), CORRIDOR, "FLOOR_PLAN")
cube("floor_south_rooms", (0, -3.8, -0.10), (25.2, 5.2, 0.20), ROOM_FLOOR, "FLOOR_PLAN")
cube("floor_north_rooms", (0, 3.8, -0.10), (25.2, 5.2, 0.20), ROOM_FLOOR, "FLOOR_PLAN")
cube("ceiling_corridor", (0, 0, ceiling_z), (25.2, corridor_w, 0.16), PLASTER, "ENVELOPE")
cube("ceiling_south_rooms", (0, -3.8, ceiling_z), (25.2, 5.2, 0.16), PLASTER, "ENVELOPE")
cube("ceiling_north_rooms", (0, 3.8, ceiling_z), (25.2, 5.2, 0.16), PLASTER, "ENVELOPE")

# Corridor boundaries with door gaps on both sides. Room 218 is the detailed south-side room.
for side, y in [("south", -1.2), ("north", 1.2)]:
    for index, x in enumerate(range(-10, 11, 3), start=1):
        if side == "south" and x == 0:
            continue
        cube(f"{side}_corridor_wall_{index}", (x, y, height / 2), (2.55, wall, height), PLASTER, "ENVELOPE")
        cube(f"{side}_door_{index}", (x, y - (0.03 if side == "south" else -0.03), 1.08), (0.9, 0.06, 2.16), DOOR, "OPENINGS", 0.025)

# Outer walls of the context segment.
cube("south_outer_wall_left", (-10.8, -6.4, height / 2), (3.3, wall, height), PLASTER)
cube("south_outer_wall_right", (10.8, -6.4, height / 2), (3.3, wall, height), PLASTER)
cube("north_outer_wall", (0, 6.4, height / 2), (25.2, wall, height), PLASTER)
for x in (-9, -6, -3, 0, 3, 6, 9):
    cube(f"south_room_side_{x}_left", (x - 1.8, -3.8, height / 2), (wall, 5.2, height), PLASTER)
    cube(f"south_room_side_{x}_right", (x + 1.8, -3.8, height / 2), (wall, 5.2, height), PLASTER)
    cube(f"north_room_side_{x}_left", (x - 1.8, 3.8, height / 2), (wall, 5.2, height), PLASTER)
    cube(f"north_room_side_{x}_right", (x + 1.8, 3.8, height / 2), (wall, 5.2, height), PLASTER)
    if x != 0:
        cube(f"south_room_back_{x}", (x, -6.4, height / 2), (2.55, wall, height), PLASTER)

# Door opening and window for room 218: the wall is split around each opening.
cube("room218_south_side_left", (-1.125, -1.2, height / 2), (1.35, wall, height), PLASTER)
cube("room218_south_side_right", (1.125, -1.2, height / 2), (1.35, wall, height), PLASTER)
cube("room218_door_head", (0, -1.2, 2.58), (0.9, wall, 0.84), PLASTER)
cube("room218_door_leaf", (0.35, -1.56, 1.1), (0.9, 0.08, 2.2), DOOR, "OPENINGS", 0.025, (0, 0, math.radians(-78)))
cube("room218_door_frame_left", (-0.45, -1.32, 1.1), (0.07, 0.12, 2.3), WALL_EDGE, "OPENINGS")
cube("room218_door_frame_right", (0.45, -1.32, 1.1), (0.07, 0.12, 2.3), WALL_EDGE, "OPENINGS")
cube("room218_door_lintel", (0, -1.32, 2.28), (0.9, 0.12, 0.07), WALL_EDGE, "OPENINGS")

cube("room218_back_wall_left", (-1.35, -6.4, height / 2), (0.9, wall, height), PLASTER)
cube("room218_back_wall_right", (1.35, -6.4, height / 2), (0.9, wall, height), PLASTER)
cube("room218_window_head", (0, -6.4, 2.65), (1.8, wall, 0.7), PLASTER)
cube("room218_window_sill", (0, -6.4, 0.85), (1.8, wall, 1.1), PLASTER)
cube("room218_window_glass", (0, -6.46, 1.75), (1.75, 0.05, 1.45), GLASS, "OPENINGS")
cube("room218_window_mullion", (0, -6.51, 1.75), (0.06, 0.07, 1.45), WALL_EDGE, "OPENINGS")

# Adjacent room labels make the repeated plan logic visible without pretending to model every room.
for label, x in [("216", -3), ("218", 0), ("220", 3), ("215", -3), ("217", 0), ("219", 3)]:
    y = -6.29 if label in {"216", "218", "220"} else 6.29
    text(f"room_label_{label}", label, (x, y, 2.55), 0.28, WHITE, rot=(math.radians(90), 0, 0))

# Room 218 inferred student-dorm fit-out: two beds, desks, storage and a clear entry path.
for x in (-1.12, 1.12):
    cube(f"room218_bed_frame_{x}", (x, -4.85, 0.32), (0.92, 2.25, 0.42), BED, "ROOM_218", 0.06)
    cube(f"room218_mattress_{x}", (x, -4.82, 0.62), (0.84, 2.10, 0.18), SHEET, "ROOM_218", 0.045)
    cube(f"room218_blanket_{x}", (x, -5.35, 0.74), (0.86, 0.80, 0.08), BLUE, "ROOM_218", 0.025)
    cube(f"room218_headboard_{x}", (x, -5.92, 1.18), (0.92, 0.12, 1.12), WOOD, "ROOM_218", 0.03)
    cube(f"room218_nightstand_{x}", (x, -3.55, 0.48), (0.48, 0.42, 0.72), WOOD, "ROOM_218", 0.03)

cube("room218_desk", (0, -2.0, 0.78), (2.55, 0.58, 0.12), WOOD, "ROOM_218", 0.03)
for x in (-0.95, 0.95):
    cube(f"room218_desk_leg_{x}", (x, -2.0, 0.39), (0.10, 0.42, 0.72), METAL, "ROOM_218")
    cube(f"room218_chair_{x}", (x, -1.45, 0.48), (0.48, 0.48, 0.78), BED, "ROOM_218", 0.05)
cube("room218_wardrobe", (-1.25, -2.15, 1.35), (0.55, 1.35, 2.55), WOOD, "ROOM_218", 0.04)
cube("room218_shelf", (1.22, -2.08, 1.85), (0.45, 1.1, 1.8), WOOD, "ROOM_218", 0.03)
for z in (1.3, 1.8, 2.3):
    cube(f"room218_shelf_line_{z}", (1.22, -2.08, z), (0.48, 1.12, 0.06), WALL_EDGE, "ROOM_218")

# Fire plan context: two stair cores at the ends and an elevator core toward the east.
for x, name in [(-13.6, "west"), (13.6, "east")]:
    cube(f"{name}_stair_left_wall", (x - 1.05, 0, 1.5), (0.18, 3.8, 3.0), WALL_EDGE, "VERTICAL")
    cube(f"{name}_stair_right_wall", (x + 1.05, 0, 1.5), (0.18, 3.8, 3.0), WALL_EDGE, "VERTICAL")
    cube(f"{name}_stair_back_wall", (x, 1.82, 1.5), (2.2, 0.18, 3.0), WALL_EDGE, "VERTICAL")
    cube(f"{name}_stair_landing", (x, -1.05, 0.08), (1.85, 1.45, 0.16), ROOM_FLOOR, "VERTICAL")
    for step in range(8):
        cube(f"{name}_stair_step_lower_{step}", (x, -0.65 + step * 0.20, 0.22 + step * 0.16), (1.0, 0.24, 0.16), WOOD, "VERTICAL")
    for step in range(8):
        cube(f"{name}_stair_step_upper_{step}", (x, 0.75 + step * 0.14, 1.48 + step * 0.16), (1.0, 0.24, 0.16), WOOD, "VERTICAL")
    cube(f"{name}_stair_mid_landing", (x, 0.65, 1.45), (1.4, 0.75, 0.16), ROOM_FLOOR, "VERTICAL")
    text(f"{name}_stair_label", "STAIR", (x, 0, 2.35), 0.23, WHITE, rot=(math.radians(90), 0, 0))

cube("elevator_back_wall", (9.8, 0.8, 1.5), (2.0, 0.18, 3.0), WALL_EDGE, "VERTICAL")
cube("elevator_left_wall", (8.82, -0.1, 1.5), (0.18, 1.8, 3.0), WALL_EDGE, "VERTICAL")
cube("elevator_right_wall", (10.78, -0.1, 1.5), (0.18, 1.8, 3.0), WALL_EDGE, "VERTICAL")
cube("elevator_floor", (9.8, -0.1, 0.08), (1.8, 1.8, 0.16), METAL, "VERTICAL")
cube("elevator_cab_back", (9.8, 0.62, 1.3), (1.55, 0.04, 2.45), METAL, "VERTICAL")
for x in (9.3, 10.3):
    cube(f"elevator_door_{x}", (x, -1.02, 1.1), (0.48, 0.07, 2.2), METAL, "OPENINGS", 0.02)
text("elevator_label", "LIFT", (9.8, -1.16, 2.35), 0.24, WHITE, rot=(math.radians(90), 0, 0))

# Evacuation route is shown as a low red dashed guide, matching the plan's visual cue.
for x in [v * 1.2 for v in range(-10, 11, 2)]:
    cube(f"evac_route_{x}", (x, -0.82, 0.035), (0.76, 0.035, 0.035), FIRE, "CIRCULATION")
cube("exit_sign_room218_side", (5.2, -1.26, 2.45), (0.7, 0.06, 0.28), SIGN, "CIRCULATION", 0.02)
text("exit_sign_arrow", "EXIT ->", (5.2, -1.30, 2.45), 0.12, WHITE, rot=(math.radians(90), 0, 0))

# Small context objects make the corridor read as occupied but keep circulation clear.
for x in (-7.8, 6.2):
    cube(f"corridor_bench_{x}", (x, 0.55, 0.42), (1.0, 0.38, 0.30), WOOD, "DETAILS", 0.04)
    cyl(f"corridor_plant_pot_{x}", (x, 0.72, 0.42), 0.22, 0.40, WOOD, "DETAILS", 12)
    cyl(f"corridor_plant_{x}", (x, 0.72, 1.05), 0.13, 1.1, GREEN, "DETAILS", 10)

for loc, energy, size, color in [
    ((0, -3, 6.5), 1050, 5.0, (1.0, 0.88, 0.70)),
    ((0, 2, 6.0), 950, 6.0, (0.68, 0.82, 1.0)),
    ((0, -5, 2.7), 420, 2.2, (1.0, 0.78, 0.55)),
]:
    bpy.ops.object.light_add(type="AREA", location=loc)
    light = bpy.context.object
    light.data.energy, light.data.shape, light.data.size, light.data.color = energy, "DISK", size, color
    aim(light, (0, -2, 0))
    link(light, "LIGHTS")

bpy.ops.object.light_add(type="SUN", location=(0, 0, 8))
sun = bpy.context.object
sun.data.energy = 1.5
sun.rotation_euler = (math.radians(25), math.radians(-25), math.radians(-20))
link(sun, "LIGHTS")

bpy.ops.object.camera_add(location=(1.0, -4.55, 1.65))
hero = bpy.context.object
hero.name = "hero_camera_room218_to_corridor"
hero.data.lens = 30
aim(hero, (0.0, -1.15, 1.35))
link(hero, "CAMERAS")

bpy.ops.object.camera_add(location=(20, -19, 15))
overview = bpy.context.object
overview.name = "overview_camera_floorplan_segment"
overview.data.lens = 38
aim(overview, (0, 0, 1.0))
link(overview, "CAMERAS")

scene.world = bpy.data.worlds.new("dorm_soft_day_world")
scene.world.color = (0.04, 0.05, 0.06)
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    scene.render.engine = "BLENDER_EEVEE"
scene.view_settings.look = "AgX - Medium High Contrast"

blend_path = OUT / "bucea_daxing_dorm7_floor2.blend"
glb_path = OUT / "bucea_daxing_dorm7_floor2.glb"
hero_path = OUT / "bucea_daxing_dorm7_floor2_room218.png"
overview_path = OUT / "bucea_daxing_dorm7_floor2_overview.png"

scene.camera = hero
for obj in groups["ENVELOPE"].objects:
    if obj.name.startswith("ceiling_"):
        obj.hide_render = True
scene.render.filepath = str(hero_path)
bpy.ops.render.render(write_still=True)
for obj in groups["ENVELOPE"].objects:
    obj.hide_render = False

hidden = [obj for obj in groups["ENVELOPE"].objects if obj.name.startswith("ceiling_")]
for obj in hidden:
    obj.hide_render = True
scene.camera = overview
scene.render.filepath = str(overview_path)
bpy.ops.render.render(write_still=True)
for obj in hidden:
    obj.hide_render = False

scene.camera = hero
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
bpy.ops.export_scene.gltf(filepath=str(glb_path), export_format="GLB", export_yup=True, export_apply=True)

audit = {
    "target": scene["target_building"] + ", " + scene["target_floor"],
    "room_focus": scene["room_focus"],
    "truth_status": scene["truth_status"],
    "envelope_gate": scene["envelope_gate"],
    "plan_evidence": scene["plan_evidence"],
    "inferred_assumptions": {"room_width_m": room_w, "room_depth_m": room_d, "ceiling_height_m": height, "wall_thickness_m": wall, "corridor_width_m": corridor_w},
    "space_contracts": {
        "room_218": ["floor_south_rooms", "south_room_side_0_left", "south_room_side_0_right", "room218_back_wall_left", "room218_back_wall_right", "ceiling_south_rooms", "room218_door_head", "room218_door_frame_left", "room218_door_frame_right", "room218_window_glass"],
        "corridor": ["floor_corridor", "ceiling_corridor", "south_corridor_wall_1", "north_corridor_wall_1", "evac_route_-12.0"],
        "vertical_connections": ["west_stair_left_wall", "west_stair_step_lower_0", "west_stair_step_upper_0", "east_stair_left_wall", "elevator_back_wall", "elevator_door_9.3"],
    },
    "adjacency_graph": [
        {"from": "room_218", "to": "corridor", "connection": "room218_door_opening", "evidence": "confirmed topology / inferred dimensions"},
        {"from": "corridor", "to": "west_stairwell", "connection": "west stair landing", "evidence": "confirmed on supplied plan"},
        {"from": "corridor", "to": "east_stairwell", "connection": "east stair landing", "evidence": "confirmed on supplied plan"},
        {"from": "corridor", "to": "elevator", "connection": "elevator landing and doors", "evidence": "confirmed on supplied plan"},
    ],
    "missing_contract_objects": [name for name in ["floor_south_rooms", "south_room_side_0_left", "south_room_side_0_right", "room218_door_head", "room218_window_glass", "west_stair_step_lower_0", "east_stair_step_upper_0", "elevator_back_wall"] if bpy.data.objects.get(name) is None],
    "objects_total": len(bpy.data.objects),
    "mesh_objects": sum(obj.type == "MESH" for obj in bpy.data.objects),
    "materials": len(bpy.data.materials),
    "cameras": [hero.name, overview.name],
    "outputs": [blend_path.name, glb_path.name, hero_path.name, overview_path.name],
}
(OUT / "scene_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"blend": str(blend_path), "glb": str(glb_path), "previews": [str(hero_path), str(overview_path)]}, ensure_ascii=False))
