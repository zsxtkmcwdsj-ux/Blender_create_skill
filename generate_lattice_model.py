"""Deterministically extrude a confirmed lattice silhouette into Blender/GLB.

Run with Blender, for example:
  Blender --background --python generate_lattice_model.py -- \
    --case-dir runs/lattice_demo_001

The input is the user-confirmed black/white mask saved by lattice_studio.html.
White pixels are solid lattice material; black pixels are openings.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import bpy
from mathutils import Vector


def script_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a 2.5D lattice model from a confirmed mask")
    parser.add_argument("--case-dir", type=Path, required=True)
    parser.add_argument("--max-grid", type=int, default=320)
    return parser.parse_args(script_args())


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_mask(path: Path, max_grid: int) -> tuple[list[list[bool]], int, int, int]:
    image = bpy.data.images.load(str(path.resolve()), check_existing=False)
    width, height = int(image.size[0]), int(image.size[1])
    if width < 2 or height < 2:
        raise ValueError("确认后的分割图尺寸无效")
    pixels = list(image.pixels[:])
    step = max(1, math.ceil(max(width, height) / max(32, max_grid)))
    sampled_width = math.ceil(width / step)
    sampled_height = math.ceil(height / step)
    occupied: list[list[bool]] = []
    for sy in range(sampled_height):
        row: list[bool] = []
        y0 = sy * step
        y1 = min(height, y0 + step)
        for sx in range(sampled_width):
            x0 = sx * step
            x1 = min(width, x0 + step)
            solid = 0
            total = 0
            for y in range(y0, y1):
                for x in range(x0, x1):
                    offset = (y * width + x) * 4
                    luminance = (pixels[offset] + pixels[offset + 1] + pixels[offset + 2]) / 3.0
                    solid += int(luminance >= 0.5 and pixels[offset + 3] >= 0.5)
                    total += 1
            row.append(solid >= max(1, math.ceil(total * 0.45)))
        occupied.append(row)
    return occupied, sampled_width, sampled_height, step


def create_extruded_grid(
    occupied: list[list[bool]],
    width_m: float,
    height_m: float,
    depth_m: float,
) -> tuple[bpy.types.Object, dict[str, Any]]:
    rows = len(occupied)
    cols = len(occupied[0]) if rows else 0
    if not rows or not cols:
        raise ValueError("确认后的分割图为空")
    solid_cells = sum(sum(1 for value in row if value) for row in occupied)
    if solid_cells < 8:
        raise ValueError("实体像素太少，不能生成模型")
    if solid_cells > rows * cols * 0.85:
        raise ValueError("实体覆盖率过高，请先擦除错误背景再生成")

    cell_x = width_m / cols
    cell_z = height_m / rows
    half_depth = depth_m / 2.0
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    vertex_index: dict[tuple[int, int, int], int] = {}

    def vertex(gx: int, gy: int, side: int) -> int:
        key = (gx, gy, side)
        if key not in vertex_index:
            x = -width_m / 2.0 + gx * cell_x
            z = height_m / 2.0 - gy * cell_z
            y = half_depth if side else -half_depth
            vertex_index[key] = len(vertices)
            vertices.append((x, y, z))
        return vertex_index[key]

    def is_solid(x: int, y: int) -> bool:
        return 0 <= y < rows and 0 <= x < cols and occupied[y][x]

    for y in range(rows):
        for x in range(cols):
            if not occupied[y][x]:
                continue
            front_tl, front_tr = vertex(x, y, 1), vertex(x + 1, y, 1)
            front_br, front_bl = vertex(x + 1, y + 1, 1), vertex(x, y + 1, 1)
            back_tl, back_tr = vertex(x, y, 0), vertex(x + 1, y, 0)
            back_br, back_bl = vertex(x + 1, y + 1, 0), vertex(x, y + 1, 0)
            faces.append((front_tl, front_tr, front_br, front_bl))
            faces.append((back_tl, back_bl, back_br, back_tr))
            if not is_solid(x - 1, y):
                faces.append((back_tl, front_tl, front_bl, back_bl))
            if not is_solid(x + 1, y):
                faces.append((front_tr, back_tr, back_br, front_br))
            if not is_solid(x, y - 1):
                faces.append((back_tl, back_tr, front_tr, front_tl))
            if not is_solid(x, y + 1):
                faces.append((front_bl, front_br, back_br, back_bl))

    mesh = bpy.data.meshes.new("LatticeSilhouetteMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(verbose=False)
    mesh.update()
    obj = bpy.data.objects.new("Lattice_Silhouette", mesh)
    bpy.context.collection.objects.link(obj)
    obj["generation_method"] = "confirmed_mask_grid_extrusion_v1"
    obj["solid_cell_count"] = solid_cells
    obj["grid_columns"] = cols
    obj["grid_rows"] = rows
    return obj, {
        "solid_cells": solid_cells,
        "grid": [cols, rows],
        "vertex_count": len(vertices),
        "face_count": len(faces),
        "solid_ratio": solid_cells / (rows * cols),
    }


def crop_to_solid_bounds(occupied: list[list[bool]]) -> tuple[list[list[bool]], list[int]]:
    rows = len(occupied)
    cols = len(occupied[0]) if rows else 0
    coordinates = [(x, y) for y, row in enumerate(occupied) for x, value in enumerate(row) if value]
    if not coordinates:
        raise ValueError("确认后的分割图没有实体")
    min_x = min(item[0] for item in coordinates)
    max_x = max(item[0] for item in coordinates)
    min_y = min(item[1] for item in coordinates)
    max_y = max(item[1] for item in coordinates)
    cropped = [row[min_x : max_x + 1] for row in occupied[min_y : max_y + 1]]
    return cropped, [min_x, min_y, max_x, max_y, cols, rows]


def create_neutral_material() -> bpy.types.Material:
    material = bpy.data.materials.new("Lattice_Dark_Neutral")
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.055, 0.035, 0.022, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.48
        bsdf.inputs["Metallic"].default_value = 0.0
    material["material_note"] = "Neutral preview only; not a measured historic material"
    return material


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def setup_preview(scene: bpy.types.Scene, width_m: float, height_m: float) -> bpy.types.Object:
    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background:
        background.inputs["Color"].default_value = (0.025, 0.032, 0.045, 1.0)
        background.inputs["Strength"].default_value = 0.55

    camera_data = bpy.data.cameras.new("PreviewCamera")
    camera = bpy.data.objects.new("PreviewCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = max(width_m, height_m) * 1.22
    camera.location = (0.0, -max(width_m, height_m) * 2.2, 0.0)
    look_at(camera, Vector((0.0, 0.0, 0.0)))

    key_data = bpy.data.lights.new("PreviewKey", type="AREA")
    key_data.energy = 180.0
    key_data.shape = "DISK"
    key_data.size = max(width_m, height_m) * 1.2
    key = bpy.data.objects.new("PreviewKey", key_data)
    scene.collection.objects.link(key)
    key.location = (-width_m * 0.55, -max(width_m, height_m), height_m * 0.75)
    look_at(key, Vector((0.0, 0.0, 0.0)))

    fill_data = bpy.data.lights.new("PreviewFill", type="AREA")
    fill_data.energy = 90.0
    fill_data.size = max(width_m, height_m)
    fill = bpy.data.objects.new("PreviewFill", fill_data)
    scene.collection.objects.link(fill)
    fill.location = (width_m * 0.7, -max(width_m, height_m) * 0.8, -height_m * 0.35)
    look_at(fill, Vector((0.0, 0.0, 0.0)))

    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    return camera


def render_previews(scene: bpy.types.Scene, camera: bpy.types.Object, output_dir: Path, width_m: float, height_m: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str((output_dir / "front_render.png").resolve())
    bpy.ops.render.render(write_still=True)

    camera.data.type = "PERSP"
    camera.data.lens = 58
    span = max(width_m, height_m)
    camera.location = (width_m * 0.72, -span * 1.75, height_m * 0.48)
    look_at(camera, Vector((0.0, 0.0, 0.0)))
    scene.render.filepath = str((output_dir / "perspective_render.png").resolve())
    bpy.ops.render.render(write_still=True)


def world_dimensions(obj: bpy.types.Object) -> list[float]:
    return [float(value) for value in obj.dimensions]


def main() -> int:
    args = parse_args()
    case_dir = args.case_dir.resolve()
    schema_path = case_dir / "analysis" / "lattice_schema.json"
    mask_path = case_dir / "vector" / "clean_mask.png"
    if not schema_path.is_file():
        raise FileNotFoundError(f"缺少结构参数：{schema_path}")
    if not mask_path.is_file():
        raise FileNotFoundError(f"缺少确认分割图：{mask_path}")

    schema = read_json(schema_path)
    width_m = float(schema["frame"]["width_mm"]) / 1000.0
    height_m = float(schema["frame"]["height_mm"]) / 1000.0
    depth_m = float(schema["bars"]["depth_mm"]) / 1000.0
    if min(width_m, height_m, depth_m) <= 0:
        raise ValueError("宽、高、进深必须大于 0")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.unit_settings.scale_length = 1.0

    collection = bpy.data.collections.new("LATTICE_MODEL")
    scene.collection.children.link(collection)
    occupied, original_cols, original_rows, sample_step = load_mask(mask_path, args.max_grid)
    occupied, solid_bounds = crop_to_solid_bounds(occupied)
    rows = len(occupied)
    cols = len(occupied[0])
    obj, stats = create_extruded_grid(occupied, width_m, height_m, depth_m)
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    collection.objects.link(obj)
    obj.data.materials.append(create_neutral_material())
    obj["source_mask"] = str(mask_path)
    obj["frame_width_mm"] = float(schema["frame"]["width_mm"])
    obj["frame_height_mm"] = float(schema["frame"]["height_mm"])
    obj["depth_mm"] = float(schema["bars"]["depth_mm"])

    model_dir = case_dir / "model"
    quality_dir = case_dir / "quality"
    model_dir.mkdir(parents=True, exist_ok=True)
    quality_dir.mkdir(parents=True, exist_ok=True)
    camera = setup_preview(scene, width_m, height_m)

    blend_path = model_dir / "lattice_window.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path.resolve()))
    render_previews(scene, camera, model_dir, width_m, height_m)

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    glb_path = model_dir / "lattice_window.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path.resolve()),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_cameras=False,
        export_lights=False,
    )

    report = {
        "passed": True,
        "case_id": schema.get("case_id"),
        "generation_method": "confirmed_mask_grid_extrusion_v1",
        "representation": "2.5D silhouette extrusion",
        "source_mask": str(mask_path),
        "source_dimensions_mm": [schema["frame"]["width_mm"], schema["bars"]["depth_mm"], schema["frame"]["height_mm"]],
        "model_dimensions_m": world_dimensions(obj),
        "mask_grid": [cols, rows],
        "mask_grid_before_solid_crop": [original_cols, original_rows],
        "solid_bounds_before_crop": solid_bounds,
        "mask_sample_step": sample_step,
        **stats,
        "limitations": [
            "单张正面照片不能恢复侧面雕刻、榫卯和真实截面",
            "当前模型用于几何轮廓、拓扑检查、数字构件归档和建筑场景装配验证",
            "材质为中性预览材质，不代表历史实测材质",
        ],
    }
    (quality_dir / "geometry_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "complete", "blend": str(blend_path), "glb": str(glb_path), "report": report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
