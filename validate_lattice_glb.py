"""Re-import a generated lattice GLB in a clean Blender process and validate it."""

from __future__ import annotations

import argparse
import bmesh
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def script_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected", type=float, nargs=3, required=True)
    args = parser.parse_args(script_args())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(args.glb.resolve()))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    if not points:
        raise ValueError("GLB 重导入后没有网格")
    minimum = [min(point[i] for point in points) for i in range(3)]
    maximum = [max(point[i] for point in points) for i in range(3)]
    dimensions = [maximum[i] - minimum[i] for i in range(3)]
    errors: list[str] = []
    for axis, (actual, expected) in enumerate(zip(dimensions, args.expected)):
        allowed = max(abs(expected) * 0.01, 1e-5)
        if abs(actual - expected) > allowed:
            errors.append(f"轴 {axis} 尺寸误差超出 1%：{actual:.6f} vs {expected:.6f}")
    deep_issues = []
    for obj in meshes:
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            non_manifold = sum(1 for edge in bm.edges if not edge.is_manifold)
            zero_area = sum(1 for face in bm.faces if face.calc_area() <= 1e-12)
            if non_manifold or zero_area:
                deep_issues.append({"object": obj.name, "non_manifold_edges": non_manifold, "zero_area_faces": zero_area})
        finally:
            bm.free()
    warnings: list[str] = []
    if deep_issues:
        warnings.append("GLB 为保留硬边法线可能拆分顶点；记录非流形边供后续实体化阶段检查")
    report = {
        "passed": not errors,
        "glb": str(args.glb.resolve()),
        "blender_version": bpy.app.version_string,
        "mesh_object_count": len(meshes),
        "bounds": {"min": minimum, "max": maximum, "dimensions": dimensions},
        "deep_mesh_issues": deep_issues,
        "errors": errors,
        "warnings": warnings,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
