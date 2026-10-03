from __future__ import annotations

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

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()


def mat(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next((n for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    if bsdf is None:
        bsdf = m.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        output = next((n for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial"), None)
        if output is not None:
            m.node_tree.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = 0.75
    return m


wood = mat("warm_oak", (0.72, 0.45, 0.22, 1))
dark_wood = mat("dark_walnut", (0.28, 0.16, 0.09, 1))
cream = mat("cream_wall", (0.86, 0.80, 0.68, 1))
tile = mat("muted_terra_tile", (0.55, 0.28, 0.20, 1))
green = mat("plant_green", (0.20, 0.42, 0.24, 1))
black = mat("matte_black", (0.03, 0.03, 0.03, 1))
metal = mat("soft_metal", (0.55, 0.55, 0.50, 1))
glass = mat("pale_glass", (0.62, 0.78, 0.88, 0.35))
white = mat("cup_white", (0.94, 0.90, 0.82, 1))
coffee = mat("coffee_brown", (0.18, 0.08, 0.035, 1))
accent = mat("sage_counter", (0.38, 0.52, 0.43, 1))
yellow = mat("warm_light", (1.0, 0.72, 0.32, 1))


def cube(name: str, loc, scale, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}_mesh"
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    return obj


def cyl(name: str, loc, radius, depth, material, vertices=12, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}_mesh"
    obj.data.materials.append(material)
    return obj


def text(name: str, body: str, loc, size, material, rot=(math.radians(90), 0, 0)):
    bpy.ops.object.text_add(location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}_curve"
    obj.data.body = body
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.extrude = 0.01
    obj.data.materials.append(material)
    return obj


root = bpy.data.collections.new("LOW_POLY_CAFE")
bpy.context.scene.collection.children.link(root)


def put(obj, collection=root):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    collection.objects.link(obj)
    return obj


# Room shell.
put(cube("floor_terracotta_tiles", (0, 0, -0.05), (8.0, 6.0, 0.1), tile))
put(cube("back_wall_cream", (0, 3.0, 1.5), (8.0, 0.12, 3.0), cream))
put(cube("left_wall_cream", (-4.0, 0, 1.5), (0.12, 6.0, 3.0), cream))
put(cube("right_half_wall_cream", (4.0, 1.1, 1.0), (0.12, 3.8, 2.0), cream))
put(cube("front_rug", (-1.4, -1.8, 0.01), (2.2, 1.2, 0.03), mat("rust_rug", (0.50, 0.17, 0.10, 1))))

# Counter zone.
put(cube("service_counter_sage", (-1.8, 2.15, 0.55), (3.3, 0.65, 1.1), accent))
put(cube("counter_wood_top", (-1.8, 2.15, 1.14), (3.45, 0.76, 0.12), wood))
put(cube("pastry_display_glass", (-0.7, 1.77, 1.45), (1.25, 0.18, 0.42), glass))
put(cube("pastry_display_base", (-0.7, 1.77, 1.18), (1.35, 0.28, 0.16), dark_wood))
for i, x in enumerate([-1.05, -0.7, -0.35]):
    put(cyl(f"round_pastry_{i+1}", (x, 1.66, 1.35), 0.12, 0.05, mat(f"pastry_{i+1}", (0.78, 0.49, 0.22, 1)), 10))

# Espresso machine and grinder.
put(cube("espresso_machine_body", (-2.7, 1.74, 1.55), (0.65, 0.35, 0.45), metal))
put(cube("espresso_machine_face", (-2.7, 1.55, 1.50), (0.55, 0.05, 0.25), black))
put(cyl("espresso_portafilter", (-2.7, 1.48, 1.38), 0.08, 0.36, black, 8, (math.radians(90), 0, 0)))
put(cyl("coffee_grinder_hopper", (-3.25, 1.77, 1.77), 0.18, 0.3, glass, 10))
put(cube("coffee_grinder_base", (-3.25, 1.77, 1.42), (0.32, 0.28, 0.38), black))

# Menu, shelves, cups.
put(cube("menu_board_black", (-1.8, 2.91, 2.25), (2.5, 0.06, 0.8), black))
text("menu_text", "COFFEE  TEA  CAKE", (-1.8, 2.86, 2.27), 0.18, white)
for z in [1.55, 1.95]:
    put(cube(f"back_shelf_{z:.2f}", (1.9, 2.88, z), (2.1, 0.16, 0.08), dark_wood))
    for i, x in enumerate([1.15, 1.55, 1.95, 2.35, 2.75]):
        put(cyl(f"shelf_cup_{z:.2f}_{i}", (x, 2.76, z + 0.14), 0.08, 0.16, white, 10))

# Tables and chairs.
for idx, (x, y) in enumerate([(1.6, -0.7), (-2.1, -1.2), (2.4, 1.0)]):
    put(cyl(f"table_{idx+1}_top", (x, y, 0.72), 0.55, 0.08, wood, 16))
    put(cyl(f"table_{idx+1}_pedestal", (x, y, 0.38), 0.08, 0.65, dark_wood, 10))
    put(cyl(f"table_{idx+1}_base", (x, y, 0.05), 0.28, 0.06, dark_wood, 12))
    for j, (dx, dy, rz) in enumerate([(0.85, 0, 0), (-0.85, 0, math.pi), (0, 0.85, math.pi / 2)]):
        put(cube(f"chair_{idx+1}_{j+1}_seat", (x + dx, y + dy, 0.42), (0.45, 0.42, 0.08), dark_wood))
        put(cube(f"chair_{idx+1}_{j+1}_back", (x + dx, y + dy, 0.78), (0.46, 0.07, 0.65), dark_wood))
        bpy.context.object.rotation_euler.z = rz

# Front window and door suggestion.
put(cube("front_window_frame_top", (2.2, -2.9, 2.0), (2.4, 0.1, 0.12), dark_wood))
put(cube("front_window_frame_bottom", (2.2, -2.9, 0.75), (2.4, 0.1, 0.12), dark_wood))
put(cube("front_window_glass", (2.2, -2.95, 1.35), (2.2, 0.04, 1.15), glass))
put(cube("entry_door_wood", (-3.1, -2.9, 1.0), (0.9, 0.12, 2.0), dark_wood))
put(cube("entry_door_glass", (-3.1, -2.97, 1.38), (0.62, 0.04, 0.85), glass))
put(cyl("door_handle", (-2.75, -3.02, 1.0), 0.04, 0.18, metal, 8, (math.radians(90), 0, 0)))

# Plants and pendant lights.
for i, (x, y) in enumerate([(-3.4, 2.25), (3.45, -2.25)]):
    put(cyl(f"plant_pot_{i+1}", (x, y, 0.22), 0.24, 0.42, mat(f"clay_pot_{i+1}", (0.45, 0.20, 0.12, 1)), 10))
    put(cyl(f"plant_stem_{i+1}", (x, y, 0.65), 0.035, 0.55, green, 7))
    for j, ang in enumerate([0, 1.6, 3.1, 4.5]):
        leaf = put(cube(f"plant_leaf_{i+1}_{j+1}", (x + math.cos(ang) * 0.18, y + math.sin(ang) * 0.18, 0.88), (0.32, 0.08, 0.04), green))
        leaf.rotation_euler.z = ang

for i, x in enumerate([-2.7, -0.9, 1.1]):
    put(cyl(f"pendant_cord_{i+1}", (x, 0.1, 2.65), 0.015, 0.65, black, 6))
    put(cyl(f"pendant_shade_{i+1}", (x, 0.1, 2.25), 0.28, 0.25, yellow, 12))
    bpy.context.object.scale.z = 0.65
    bpy.ops.object.light_add(type="POINT", location=(x, 0.1, 2.05))
    light = bpy.context.object
    light.name = f"warm_pendant_light_{i+1}"
    light.data.energy = 180
    light.data.color = (1.0, 0.78, 0.45)
    put(light)

# Simple floor tile grooves.
for x in [i * 0.8 - 4 for i in range(11)]:
    put(cube(f"tile_groove_x_{x:.1f}", (x, 0, 0.015), (0.015, 6.0, 0.01), black))
for y in [i * 0.8 - 3 for i in range(9)]:
    put(cube(f"tile_groove_y_{y:.1f}", (0, y, 0.016), (8.0, 0.015, 0.01), black))

# Camera and render setup.
bpy.ops.object.light_add(type="AREA", location=(0, -2.5, 4.5))
area = bpy.context.object
area.name = "large_softbox_front"
area.data.energy = 450
area.data.size = 5
put(area)

bpy.ops.object.camera_add(location=(5.7, -6.5, 4.3), rotation=(math.radians(62), 0, math.radians(41)))
camera = bpy.context.object
bpy.context.scene.camera = camera
direction = Vector((0, 0, 1.1)) - camera.location
camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
camera.data.type = "ORTHO"
camera.data.ortho_scale = 7.1

scene = bpy.context.scene
scene.render.resolution_x = 1600
scene.render.resolution_y = 1200
scene.render.film_transparent = False
scene.world = bpy.data.worlds.new("soft_gray_world")
scene.world.color = (0.78, 0.80, 0.82)
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except TypeError:
    scene.render.engine = "BLENDER_EEVEE"

blend_path = OUT / "low_poly_cafe.blend"
glb_path = OUT / "low_poly_cafe.glb"
png_path = OUT / "low_poly_cafe_preview.png"

bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
bpy.ops.export_scene.gltf(filepath=str(glb_path), export_format="GLB", export_yup=True)
scene.render.filepath = str(png_path)
bpy.ops.render.render(write_still=True)

print({"blend": str(blend_path), "glb": str(glb_path), "preview": str(png_path)})
