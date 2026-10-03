#!/usr/bin/env python3
"""Blender 场景基线、审计与不可变内容验证工具。

必须由 Blender 的 Python 运行，例如：
blender project.blend --background --python blender_scene_guard.py -- snapshot --output baseline.json
"""

from __future__ import annotations

import argparse
import bmesh
import hashlib
import json
import os
from array import array
from pathlib import Path
import struct
import sys
import traceback
from typing import Any, Iterable

try:
    import bpy
except ImportError as exc:  # pragma: no cover - 仅在错误运行环境触发
    raise SystemExit("本脚本必须使用 Blender Python 运行。") from exc


SCHEMA_VERSION = 1


def _arguments_after_double_dash() -> list[str]:
    """只读取 Blender 命令行中 `--` 后的脚本参数。"""
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1 :]


def _default_output(suffix: str) -> Path:
    """根据当前 blend 文件生成默认报告路径。"""
    if bpy.data.filepath:
        source = Path(bpy.data.filepath)
        return source.with_name(f"{source.stem}_{suffix}.json")
    return Path.cwd() / f"untitled_{suffix}.json"


def _update_text(hasher: "hashlib._Hash", value: Any) -> None:
    """以确定性 UTF-8 文本更新哈希。"""
    hasher.update(str(value).encode("utf-8", errors="surrogatepass"))
    hasher.update(b"\0")


def _update_floats(hasher: "hashlib._Hash", values: Iterable[float]) -> None:
    """使用双精度二进制格式更新浮点序列，避免区域设置差异。"""
    for value in values:
        hasher.update(struct.pack("<d", float(value)))


def _mesh_digest(mesh: "bpy.types.Mesh") -> str:
    """计算不包含材质槽的网格拓扑与顶点坐标哈希。"""
    digest = hashlib.sha256()
    _update_text(digest, mesh.name_full)
    _update_text(digest, len(mesh.vertices))
    _update_text(digest, len(mesh.edges))
    _update_text(digest, len(mesh.loops))
    _update_text(digest, len(mesh.polygons))

    if mesh.vertices:
        coordinates = array("f", [0.0]) * (len(mesh.vertices) * 3)
        mesh.vertices.foreach_get("co", coordinates)
        digest.update(coordinates.tobytes())
    if mesh.edges:
        edge_vertices = array("i", [0]) * (len(mesh.edges) * 2)
        mesh.edges.foreach_get("vertices", edge_vertices)
        digest.update(edge_vertices.tobytes())
    if mesh.loops:
        loop_vertices = array("i", [0]) * len(mesh.loops)
        mesh.loops.foreach_get("vertex_index", loop_vertices)
        digest.update(loop_vertices.tobytes())
    if mesh.polygons:
        loop_starts = array("i", [0]) * len(mesh.polygons)
        loop_totals = array("i", [0]) * len(mesh.polygons)
        mesh.polygons.foreach_get("loop_start", loop_starts)
        mesh.polygons.foreach_get("loop_total", loop_totals)
        digest.update(loop_starts.tobytes())
        digest.update(loop_totals.tobytes())
    return digest.hexdigest()


def transform_geometry_hash(scene: "bpy.types.Scene") -> str:
    """计算场景对象变换、层级、可见状态和网格几何的组合哈希。"""
    digest = hashlib.sha256()
    mesh_cache: dict[str, str] = {}

    for obj in sorted(scene.objects, key=lambda item: item.name_full):
        _update_text(digest, obj.name_full)
        _update_text(digest, obj.type)
        _update_text(digest, obj.parent.name_full if obj.parent else "")
        _update_text(digest, obj.data.name_full if obj.data else "")
        _update_text(digest, bool(obj.hide_render))
        _update_text(digest, bool(obj.hide_viewport))
        _update_floats(digest, (value for row in obj.matrix_world for value in row))
        if obj.type == "MESH" and obj.data:
            mesh = obj.data
            if mesh.name_full not in mesh_cache:
                mesh_cache[mesh.name_full] = _mesh_digest(mesh)
            _update_text(digest, mesh_cache[mesh.name_full])
    return digest.hexdigest()


def light_hash(scene: "bpy.types.Scene") -> str:
    """计算灯光数据与世界节点的哈希。"""
    digest = hashlib.sha256()
    for obj in sorted((item for item in scene.objects if item.type == "LIGHT"), key=lambda item: item.name_full):
        light = obj.data
        _update_text(digest, obj.name_full)
        _update_text(digest, light.type)
        _update_floats(digest, (value for row in obj.matrix_world for value in row))
        _update_floats(digest, light.color)
        for attr in ("energy", "shadow_soft_size", "size", "size_y", "spot_size", "spot_blend"):
            _update_text(digest, getattr(light, attr, None))

    world = scene.world
    if world:
        _update_text(digest, world.name_full)
        _update_text(digest, world.color[:])
        world_tree = getattr(world, "node_tree", None)
        if world_tree:
            for node in sorted(world_tree.nodes, key=lambda item: item.name):
                _update_text(digest, node.name)
                _update_text(digest, node.bl_idname)
                for socket in node.inputs:
                    if not socket.is_linked and hasattr(socket, "default_value"):
                        _update_text(digest, socket.name)
                        _update_text(digest, socket.default_value)
    return digest.hexdigest()


def animation_hash(scene: "bpy.types.Scene") -> str:
    """计算帧设置、当前相机、动作与关键帧哈希。"""
    digest = hashlib.sha256()
    for value in (scene.frame_start, scene.frame_end, scene.render.fps, scene.render.fps_base):
        _update_text(digest, value)
    _update_text(digest, scene.camera.name_full if scene.camera else "")

    for action in sorted(bpy.data.actions, key=lambda item: item.name_full):
        _update_text(digest, action.name_full)
        for layer in getattr(action, "layers", []):
            _update_text(digest, layer.name)
            for strip in getattr(layer, "strips", []):
                _update_text(digest, strip.name)
        # 兼容传统 Action F-Curve 数据结构。
        for curve in sorted(getattr(action, "fcurves", []), key=lambda item: (item.data_path, item.array_index)):
            _update_text(digest, curve.data_path)
            _update_text(digest, curve.array_index)
            for point in curve.keyframe_points:
                _update_floats(digest, point.co)
                _update_floats(digest, point.handle_left)
                _update_floats(digest, point.handle_right)
                _update_text(digest, point.interpolation)
    return digest.hexdigest()


def material_assignment_hash(scene: "bpy.types.Scene") -> str:
    """计算对象材质槽映射，用于可选的严格材质验证。"""
    digest = hashlib.sha256()
    for obj in sorted((item for item in scene.objects if item.type == "MESH"), key=lambda item: item.name_full):
        _update_text(digest, obj.name_full)
        for slot in obj.material_slots:
            _update_text(digest, slot.material.name_full if slot.material else "")
    return digest.hexdigest()


def _image_record(image: "bpy.types.Image") -> dict[str, Any]:
    """生成贴图路径与打包状态记录。"""
    raw_path = image.filepath or ""
    try:
        absolute = bpy.path.abspath(raw_path, library=image.library) if raw_path else ""
    except Exception:
        absolute = bpy.path.abspath(raw_path) if raw_path else ""
    packed = bool(image.packed_file)
    external_source = image.source in {"FILE", "MOVIE", "SEQUENCE", "TILED"}
    exists = (not external_source) or packed or bool(absolute and os.path.isfile(absolute))
    return {
        "name": image.name_full,
        "source": image.source,
        "size": [int(image.size[0]), int(image.size[1])],
        "filepath": raw_path,
        "absolute_path": absolute,
        "packed": packed,
        "exists": exists,
    }


def material_audit() -> dict[str, Any]:
    """审计材质输出、脚本节点与图像完整性。"""
    records: list[dict[str, Any]] = []
    for material in sorted(bpy.data.materials, key=lambda item: item.name_full):
        node_tree = getattr(material, "node_tree", None)
        record: dict[str, Any] = {
            "name": material.name_full,
            "users": int(material.users),
            "has_node_tree": bool(node_tree),
            "output_connected": False,
            "script_nodes": [],
            "images": [],
        }
        if node_tree:
            for node in node_tree.nodes:
                if node.bl_idname == "ShaderNodeOutputMaterial":
                    surface = node.inputs.get("Surface")
                    record["output_connected"] |= bool(surface and surface.is_linked)
                if node.bl_idname in {"ShaderNodeScript", "ShaderNodeTexIES"}:
                    record["script_nodes"].append(node.name)
                if node.bl_idname == "ShaderNodeTexImage" and getattr(node, "image", None):
                    record["images"].append(_image_record(node.image))
        records.append(record)
    return {
        "materials": records,
        "missing_images": sorted(
            {image.name_full for image in bpy.data.images if not _image_record(image)["exists"]}
        ),
    }


def deep_mesh_audit(scene: "bpy.types.Scene") -> list[dict[str, Any]]:
    """使用 BMesh 检查非流形边和零面积面；大型场景可能较慢。"""
    results: list[dict[str, Any]] = []
    checked_data: set[str] = set()
    for obj in sorted((item for item in scene.objects if item.type == "MESH" and item.data), key=lambda item: item.name_full):
        mesh = obj.data
        if mesh.name_full in checked_data:
            continue
        checked_data.add(mesh.name_full)
        bm = bmesh.new()
        try:
            bm.from_mesh(mesh)
            non_manifold = sum(1 for edge in bm.edges if not edge.is_manifold)
            zero_area = sum(1 for face in bm.faces if face.calc_area() <= 1e-12)
            if non_manifold or zero_area:
                results.append({
                    "mesh": mesh.name_full,
                    "non_manifold_edges": non_manifold,
                    "zero_area_faces": zero_area,
                })
        finally:
            bm.free()
    return results


def build_manifest(deep: bool = False) -> dict[str, Any]:
    """构建可序列化的完整场景清单。"""
    scene = bpy.context.scene
    negative_scale = [
        obj.name_full
        for obj in scene.objects
        if any(float(value) < 0.0 for value in obj.scale)
    ]
    smooth_without_sharp: list[str] = []
    for obj in scene.objects:
        if obj.type != "MESH" or not obj.data or not obj.data.polygons:
            continue
        smooth_count = sum(1 for polygon in obj.data.polygons if polygon.use_smooth)
        sharp_attribute = obj.data.attributes.get("sharp_edge")
        if smooth_count == len(obj.data.polygons) and sharp_attribute is None:
            smooth_without_sharp.append(obj.name_full)

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "blend_file": bpy.data.filepath,
        "blender_version": bpy.app.version_string,
        "scene": bpy.context.scene.name_full,
        "object_count": len(scene.objects),
        "mesh_object_count": sum(1 for obj in scene.objects if obj.type == "MESH"),
        "mesh_data_count": len(bpy.data.meshes),
        "material_count": len(bpy.data.materials),
        "frame_range": [int(scene.frame_start), int(scene.frame_end)],
        "fps": float(scene.render.fps / scene.render.fps_base),
        "active_camera": scene.camera.name_full if scene.camera else None,
        "hashes": {
            "transform_geometry": transform_geometry_hash(scene),
            "lights_world": light_hash(scene),
            "animation": animation_hash(scene),
            "material_assignments": material_assignment_hash(scene),
        },
        "negative_scale_objects": negative_scale,
        "smooth_without_sharp_attribute": smooth_without_sharp,
        "materials": material_audit(),
    }
    if deep:
        manifest["deep_mesh_issues"] = deep_mesh_audit(scene)
    return manifest


def write_json(path: Path, data: dict[str, Any]) -> None:
    """以 UTF-8 安全写入 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def verify_manifest(current: dict[str, Any], baseline: dict[str, Any], strict_materials: bool) -> dict[str, Any]:
    """比较当前清单与基线中的受保护字段。"""
    checks = {
        "transform_geometry": current["hashes"]["transform_geometry"] == baseline["hashes"]["transform_geometry"],
        "lights_world": current["hashes"]["lights_world"] == baseline["hashes"]["lights_world"],
        "animation": current["hashes"]["animation"] == baseline["hashes"]["animation"],
        "frame_range": current["frame_range"] == baseline["frame_range"],
        "fps": current["fps"] == baseline["fps"],
        "object_count": current["object_count"] == baseline["object_count"],
        "mesh_object_count": current["mesh_object_count"] == baseline["mesh_object_count"],
    }
    if strict_materials:
        checks["material_assignments"] = (
            current["hashes"]["material_assignments"] == baseline["hashes"]["material_assignments"]
        )
    return {
        "passed": all(checks.values()),
        "strict_materials": strict_materials,
        "checks": checks,
        "baseline_file": baseline.get("blend_file"),
        "current_file": current.get("blend_file"),
        "current": current,
    }


def parse_args() -> argparse.Namespace:
    """解析脚本参数。"""
    parser = argparse.ArgumentParser(description="Blender 场景基线、审计与验证工具")
    parser.add_argument("command", choices=("snapshot", "audit", "verify"))
    parser.add_argument("--output", type=Path, help="输出 JSON 路径")
    parser.add_argument("--baseline", type=Path, help="verify 使用的基线 JSON")
    parser.add_argument("--deep", action="store_true", help="执行较慢的 BMesh 非流形检查")
    parser.add_argument("--strict-materials", action="store_true", help="同时要求材质槽映射不变")
    return parser.parse_args(_arguments_after_double_dash())


def main() -> int:
    """执行命令并返回进程状态。"""
    args = parse_args()
    current = build_manifest(deep=args.deep)

    if args.command == "snapshot":
        output = args.output or _default_output("baseline")
        write_json(output, current)
        print(json.dumps({"passed": True, "output": str(output), "hashes": current["hashes"]}, ensure_ascii=False))
        return 0

    if args.command == "audit":
        output = args.output or _default_output("audit")
        write_json(output, current)
        print(json.dumps({"passed": True, "output": str(output)}, ensure_ascii=False))
        return 0

    if not args.baseline:
        raise ValueError("verify 命令必须提供 --baseline。")
    if not args.baseline.is_file():
        raise FileNotFoundError(f"基线文件不存在：{args.baseline}")
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    result = verify_manifest(current, baseline, args.strict_materials)
    output = args.output or _default_output("verification")
    write_json(output, result)
    print(json.dumps({"passed": result["passed"], "output": str(output), "checks": result["checks"]}, ensure_ascii=False))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # 确保后台运行时返回明确错误
        print(json.dumps({
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from exc
