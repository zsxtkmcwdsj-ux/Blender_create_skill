#!/usr/bin/env python3
"""索引 Blender 资产目录中的 `.blend` 材质名称，不追加任何数据。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import traceback

try:
    import bpy
except ImportError as exc:  # pragma: no cover
    raise SystemExit("本脚本必须使用 Blender Python 运行。") from exc


def _script_args() -> list[str]:
    """返回 `--` 后的脚本参数。"""
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def _configured_asset_roots() -> list[Path]:
    """读取当前 Blender 偏好设置中的用户资产库目录。"""
    roots: list[Path] = []
    libraries = getattr(bpy.context.preferences.filepaths, "asset_libraries", [])
    for library in libraries:
        path = Path(bpy.path.abspath(library.path)).expanduser()
        if path.is_dir():
            roots.append(path.resolve())
    return roots


def _collect_blend_files(roots: list[Path], max_files: int) -> list[Path]:
    """确定性收集 `.blend` 文件并限制数量。"""
    files: set[Path] = set()
    for root in roots:
        if root.is_file() and root.suffix.lower() == ".blend":
            files.add(root.resolve())
        elif root.is_dir():
            for path in root.rglob("*.blend"):
                files.add(path.resolve())
                if len(files) >= max_files:
                    break
        if len(files) >= max_files:
            break
    return sorted(files, key=lambda item: str(item).casefold())


def _list_materials(path: Path) -> dict[str, object]:
    """只读加载库目录，返回材质名称；不把材质追加到当前文件。"""
    try:
        with bpy.data.libraries.load(str(path), link=False) as (data_from, _data_to):
            names = sorted(data_from.materials, key=str.casefold)
        return {"file": str(path), "materials": names, "count": len(names), "error": None}
    except Exception as exc:
        return {
            "file": str(path),
            "materials": [],
            "count": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _write_json(path: Path, data: dict[str, object]) -> None:
    """原子写入索引文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="索引 Blender `.blend` 材质资产库")
    parser.add_argument("--roots", type=Path, nargs="*", help="一个或多个资产库目录或 `.blend` 文件")
    parser.add_argument("--output", type=Path, default=Path.cwd() / "material_library_index.json")
    parser.add_argument("--max-files", type=int, default=10000)
    return parser.parse_args(_script_args())


def main() -> int:
    """生成材质索引与重复名称映射。"""
    args = parse_args()
    if args.max_files <= 0:
        raise ValueError("--max-files 必须大于 0。")

    roots = [path.expanduser().resolve() for path in (args.roots or [])]
    if not roots:
        roots = _configured_asset_roots()
    if not roots:
        raise ValueError("没有提供 --roots，且 Blender 中未配置可用资产库。")

    missing_roots = [str(path) for path in roots if not path.exists()]
    valid_roots = [path for path in roots if path.exists()]
    if not valid_roots:
        raise FileNotFoundError("所有资产库路径均不存在。")

    files = _collect_blend_files(valid_roots, args.max_files)
    records = [_list_materials(path) for path in files]
    reverse: dict[str, list[str]] = {}
    for record in records:
        for name in record["materials"]:
            reverse.setdefault(str(name), []).append(str(record["file"]))

    result: dict[str, object] = {
        "blender_version": bpy.app.version_string,
        "roots": [str(path) for path in roots],
        "missing_roots": missing_roots,
        "blend_file_count": len(files),
        "material_name_count": len(reverse),
        "libraries": records,
        "materials": {name: paths for name, paths in sorted(reverse.items(), key=lambda item: item[0].casefold())},
    }
    _write_json(args.output, result)
    failed = sum(1 for record in records if record["error"])
    print(json.dumps({
        "passed": failed == 0,
        "output": str(args.output),
        "blend_files": len(files),
        "unique_materials": len(reverse),
        "failed_files": failed,
    }, ensure_ascii=False))
    return 0 if failed == 0 else 2


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
