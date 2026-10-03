#!/usr/bin/env python3
"""在独立 Blender 后台进程中重导入并验证 GLB。"""

from __future__ import annotations

import argparse
import bmesh
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any

try:
    import bpy
    from mathutils import Vector
except ImportError as exc:  # pragma: no cover
    raise SystemExit("本脚本必须使用 Blender Python 运行。") from exc


def _script_args() -> list[str]:
    """返回 `--` 后的脚本参数。"""
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="GLB 重导入验证")
    parser.add_argument("--glb", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-bounds", type=float, nargs=3, metavar=("X", "Y", "Z"))
    parser.add_argument("--tolerance", type=float, default=0.01, help="尺寸相对误差，默认 1%%")
    parser.add_argument("--deep", action="store_true", help="检查非流形边和零面积面")
    parser.add_argument("--allow-live", action="store_true", help="允许在非后台 Blender 中清空当前场景，不推荐")
    return parser.parse_args(_script_args())


def _world_bounds(objects: list["bpy.types.Object"]) -> tuple[list[float], list[float], list[float]]:
    """计算所有可见网格对象的世界包围盒。"""
    points: list[Vector] = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not points:
        raise ValueError("GLB 导入后没有网格对象。")
    minimum = [min(point[index] for point in points) for index in range(3)]
    maximum = [max(point[index] for point in points) for index in range(3)]
    dimensions = [maximum[index] - minimum[index] for index in range(3)]
    return minimum, maximum, dimensions


def _image_record(image: "bpy.types.Image") -> dict[str, Any]:
    """记录 GLB 图像的存在与打包状态。"""
    raw = image.filepath or ""
    absolute = bpy.path.abspath(raw) if raw else ""
    packed = bool(image.packed_file)
    return {
        "name": image.name_full,
        "size": [int(image.size[0]), int(image.size[1])],
        "filepath": raw,
        "packed": packed,
        "exists": packed or bool(absolute and os.path.isfile(absolute)),
    }


def _deep_mesh_issues(objects: list["bpy.types.Object"]) -> list[dict[str, Any]]:
    """检查导入网格的非流形边和零面积面。"""
    issues: list[dict[str, Any]] = []
    seen: set[str] = set()
    for obj in objects:
        if obj.type != "MESH" or not obj.data or obj.data.name_full in seen:
            continue
        seen.add(obj.data.name_full)
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            non_manifold = sum(1 for edge in bm.edges if not edge.is_manifold)
            zero_area = sum(1 for face in bm.faces if face.calc_area() <= 1e-12)
            if non_manifold or zero_area:
                issues.append({
                    "mesh": obj.data.name_full,
                    "non_manifold_edges": non_manifold,
                    "zero_area_faces": zero_area,
                })
        finally:
            bm.free()
    return issues


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """原子写入验证报告。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    """清空临时场景、导入 GLB 并执行验证。"""
    args = parse_args()
    if not args.glb.is_file():
        raise FileNotFoundError(f"GLB 不存在：{args.glb}")
    if args.tolerance < 0:
        raise ValueError("--tolerance 不能小于 0。")
    if not bpy.app.background and not args.allow_live:
        raise RuntimeError("为保护当前工程，本脚本默认只允许在 --background Blender 中运行。")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(args.glb))
    scene = bpy.context.scene
    objects = list(scene.objects)
    minimum, maximum, dimensions = _world_bounds(objects)

    errors: list[str] = []
    warnings: list[str] = []
    if args.expected_bounds:
        for axis, (actual, expected) in enumerate(zip(dimensions, args.expected_bounds)):
            allowed = max(abs(expected) * args.tolerance, 1e-6)
            if abs(actual - expected) > allowed:
                errors.append(
                    f"轴 {axis} 尺寸 {actual:.6f} 与预期 {expected:.6f} 的差值超过 {allowed:.6f}。"
                )

    images = [_image_record(image) for image in bpy.data.images]
    missing_images = [record["name"] for record in images if not record["exists"]]
    if missing_images:
        errors.append("存在缺失图像：" + ", ".join(missing_images))

    negative_scale = [obj.name_full for obj in objects if any(float(value) < 0.0 for value in obj.scale)]
    if negative_scale:
        warnings.append("存在负缩放对象：" + ", ".join(negative_scale))

    deep_issues = _deep_mesh_issues(objects) if args.deep else []
    if deep_issues:
        warnings.append("深度网格检查发现非流形边或零面积面。")

    report: dict[str, Any] = {
        "passed": not errors,
        "glb": str(args.glb.resolve()),
        "blender_version": bpy.app.version_string,
        "object_count": len(objects),
        "mesh_object_count": sum(1 for obj in objects if obj.type == "MESH"),
        "material_count": len(bpy.data.materials),
        "image_count": len(bpy.data.images),
        "light_count": sum(1 for obj in objects if obj.type == "LIGHT"),
        "camera_count": sum(1 for obj in objects if obj.type == "CAMERA"),
        "action_count": len(bpy.data.actions),
        "bounds": {"min": minimum, "max": maximum, "dimensions": dimensions},
        "images": images,
        "negative_scale_objects": negative_scale,
        "deep_mesh_issues": deep_issues,
        "errors": errors,
        "warnings": warnings,
    }
    _write_json(args.output, report)
    print(json.dumps({
        "passed": report["passed"],
        "output": str(args.output),
        "dimensions": dimensions,
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(json.dumps({
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from exc
