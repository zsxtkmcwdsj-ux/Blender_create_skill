from __future__ import annotations

import argparse
import base64
import binascii
import json
import mimetypes
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
GROUND_TRUTH_EXPERIMENT = Path("/Users/san/Desktop/text to bim/传统窗棂实验_阶段1至4_20260823")
DATASET_MANIFEST = GROUND_TRUTH_EXPERIMENT / "00_实验设计/dataset_manifest.json"
GROUND_TRUTH_SELECTION = GROUND_TRUTH_EXPERIMENT / "00_实验设计/人工真值三类测验_18张.json"
CSAM_HANDOFFS = RUNS / "_csam_handoffs"
CURRENT_GROUND_TRUTH_ROOT = GROUND_TRUTH_EXPERIMENT / "09_三技术统一测试集_30张/01.5_人工真值_待人工复核"
LEGACY_GROUND_TRUTH_ROOT = GROUND_TRUTH_EXPERIMENT / "02_人工真值_待人工复核"
IMPORTED_GROUND_TRUTH_ROOT = CURRENT_GROUND_TRUTH_ROOT / "_拖拽导入文件夹"
UNIFIED_INPUT_ROOT = GROUND_TRUTH_EXPERIMENT / "09_三技术统一测试集_30张/00_统一输入"
JOBS: dict[str, dict[str, Any]] = {}
MAX_REQUEST_BYTES = 40 * 1024 * 1024
MAX_IMAGE_BYTES = 12 * 1024 * 1024
IMAGE_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


def clean_case_id(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())[:80].strip("_")
    return value or time.strftime("scene_%Y%m%d_%H%M%S")


def relative(path: Path | None) -> str | None:
    if not path:
        return None
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def first_file(pattern: str, case_dir: Path) -> Path | None:
    return next(iter(sorted(case_dir.glob(pattern))), None)


def ground_truth_case_dir(case_id: str) -> Path:
    """Return the active annotation directory, with a read-compatible legacy fallback.

    The active 30-image experiment was reorganised under ``09_三技术统一测试集_30张``.
    Keeping this resolution in one place prevents the research pages from silently
    loading a stale copy of an image or a manual mask.
    """
    imported = IMPORTED_GROUND_TRUTH_ROOT / case_id
    if imported.is_dir():
        return imported
    current = CURRENT_GROUND_TRUTH_ROOT / case_id
    if current.is_dir() or not (LEGACY_GROUND_TRUTH_ROOT / case_id).is_dir():
        return current
    return LEGACY_GROUND_TRUTH_ROOT / case_id


def dataset_source_path(case_id: str) -> Path:
    """Resolve a frozen 30-case source without requiring a GT annotation folder."""
    annotated_source = ground_truth_case_dir(case_id) / "source.png"
    if annotated_source.is_file():
        return annotated_source
    for extension in (".png", ".jpg", ".jpeg", ".webp"):
        candidate = UNIFIED_INPUT_ROOT / f"{case_id}{extension}"
        if candidate.is_file():
            return candidate
    return annotated_source


def archive_case_dir(case_id: str) -> None:
    case_dir = RUNS / case_id
    if not case_dir.exists():
        return
    archive_root = RUNS / "_archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    target = archive_root / f"{case_id}_{time.strftime('%Y%m%d_%H%M%S')}"
    suffix = 1
    while target.exists():
        suffix += 1
        target = archive_root / f"{case_id}_{time.strftime('%Y%m%d_%H%M%S')}_{suffix}"
    shutil.move(str(case_dir), str(target))


def decode_image_data_url(value: str) -> tuple[bytes, str]:
    """Decode one browser canvas/file data URL with strict MIME and size limits."""
    match = re.fullmatch(r"data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=\r\n]+)", value or "")
    if not match:
        raise ValueError("图片必须是 PNG、JPEG 或 WebP data URL")
    mime_type = match.group(1)
    try:
        data = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("图片数据不是有效的 base64") from exc
    if not data:
        raise ValueError("图片数据为空")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("单张图片不能超过 12 MB")
    return data, IMAGE_EXTENSIONS[mime_type]


def read_dataset_records() -> list[dict[str, Any]]:
    if not DATASET_MANIFEST.is_file():
        raise FileNotFoundError("窗棂数据集尚未初始化")
    manifest = json.loads(DATASET_MANIFEST.read_text(encoding="utf-8"))
    return list(manifest.get("records", []))


def dataset_cases(records: list[dict[str, Any]], ground_truth_ids: set[str] | None = None) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    category_counts: dict[str, int] = {}
    ground_truth_ids = ground_truth_ids or set()
    for record in records:
        case_id = clean_case_id(str(record.get("case_id") or ""))
        case_dir = ground_truth_case_dir(case_id)
        status_path = case_dir / "status.json"
        status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.is_file() else {"status": "missing"}
        category = str(record.get("category") or "未分类")
        category_counts[category] = category_counts.get(category, 0) + 1
        cases.append({
            **record,
            "category_case_number": category_counts[category],
            "status": status.get("status"),
            "has_saved_mask": (case_dir / "manual_mask.png").is_file(),
            "ground_truth_selected": case_id in ground_truth_ids,
            "ground_truth_approved": bool(status.get("is_ground_truth")) and not bool(status.get("second_review_required")),
        })
    return cases


def imported_ground_truth_cases() -> list[dict[str, Any]]:
    """List only images explicitly added through the drag-and-drop annotation folder."""
    IMPORTED_GROUND_TRUTH_ROOT.mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, Any]] = []
    case_dirs = sorted(
        (path for path in IMPORTED_GROUND_TRUTH_ROOT.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for index, case_dir in enumerate(case_dirs, 1):
        source_path = first_file("source.*", case_dir)
        if source_path is None:
            continue
        metadata_path = case_dir / "import.json"
        status_path = case_dir / "status.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
        status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.is_file() else {"status": "not_started"}
        cases.append({
            "case_id": case_dir.name,
            "category": "我的标注文件夹",
            "category_case_number": index,
            "filename": str(metadata.get("original_filename") or source_path.name),
            "working_width": int(metadata.get("working_width") or 0),
            "working_height": int(metadata.get("working_height") or 0),
            "status": status.get("status"),
            "has_saved_mask": (case_dir / "manual_mask.png").is_file(),
            "ground_truth_selected": True,
            "ground_truth_approved": bool(status.get("is_ground_truth")) and not bool(status.get("second_review_required")),
            "imported_at": metadata.get("imported_at"),
        })
    return cases


def import_ground_truth_image(payload: dict[str, Any]) -> dict[str, Any]:
    image_value = payload.get("image")
    if not isinstance(image_value, str):
        raise ValueError("缺少待导入图片")
    image_data, image_ext = decode_image_data_url(image_value)
    original_filename = Path(str(payload.get("filename") or f"未命名{image_ext}")).name
    base = clean_case_id(Path(original_filename).stem)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    case_id = clean_case_id(f"GTU_{stamp}_{base}")
    case_dir = IMPORTED_GROUND_TRUTH_ROOT / case_id
    suffix = 1
    while case_dir.exists():
        suffix += 1
        case_id = clean_case_id(f"GTU_{stamp}_{base}_{suffix}")
        case_dir = IMPORTED_GROUND_TRUTH_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=False)
    (case_dir / f"source{image_ext}").write_bytes(image_data)
    metadata = {
        "case_id": case_id,
        "original_filename": original_filename,
        "working_width": int(payload.get("width") or 0),
        "working_height": int(payload.get("height") or 0),
        "imported_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "input_mode": "ground_truth_drag_drop_folder",
    }
    (case_dir / "import.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        **metadata,
        "category": "我的标注文件夹",
        "category_case_number": 1,
        "filename": original_filename,
        "status": "not_started",
        "has_saved_mask": False,
        "ground_truth_selected": True,
        "ground_truth_approved": False,
    }


def save_csam_handoff(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("application_validated") is not True and payload.get("ready_for_3d") is not True:
        raise ValueError("请先确认当前Mask可进入三维重建")
    case_id = clean_case_id(str(payload.get("case_id") or "csam_case"))
    source_value = payload.get("source")
    mask_value = payload.get("mask")
    if not isinstance(source_value, str) or not isinstance(mask_value, str):
        raise ValueError("缺少三维重建所需的原图或Mask")
    source_data, source_ext = decode_image_data_url(source_value)
    mask_data, _ = decode_image_data_url(mask_value)
    stage = clean_case_id(str(payload.get("stage") or "C6"))
    handoff_id = f"{case_id}_{stage}_{time.strftime('%Y%m%d_%H%M%S')}"
    handoff_dir = CSAM_HANDOFFS / handoff_id
    handoff_dir.mkdir(parents=True, exist_ok=False)
    (handoff_dir / f"source{source_ext}").write_bytes(source_data)
    (handoff_dir / "c6_mask.png").write_bytes(mask_data)
    metadata = {
        "handoff_id": handoff_id,
        "case_id": case_id,
        "method": str(payload.get("method_label") or "障碍感知与拓扑反馈窗棂分割"),
        "stage": str(payload.get("stage") or "C6"),
        "handoff_kind": str(payload.get("handoff_kind") or "segmentation_mask"),
        "analysis_method": str(payload.get("analysis_method") or "lattice_mask_handoff"),
        "algorithm_version": str(payload.get("algorithm_version") or "lattice_oatf_v2_zero_shot"),
        "source_output_dir": str(payload.get("source_output_dir") or ""),
        "application_validation": {
            "status": "accepted_for_downstream_reconstruction",
            "note": str(payload.get("validation_note") or "").strip(),
            "scope": "应用验收，不等同于论文精度验证",
        },
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (handoff_dir / "handoff.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": "complete",
        "handoff_id": handoff_id,
        "application_url": f"lattice_studio.html?csam_handoff={urllib.parse.quote(handoff_id)}",
        "metadata": metadata,
    }


def lattice_artifacts(case_dir: Path) -> dict[str, Any]:
    analysis_dir = case_dir / "analysis"
    source_dir = case_dir / "source"
    vector_dir = case_dir / "vector"
    model_dir = case_dir / "model"
    quality_dir = case_dir / "quality"
    original = first_file("original.*", source_dir)
    glb = model_dir / "lattice_window.glb"
    blend = model_dir / "lattice_window.blend"
    preview = model_dir / "perspective_render.png"
    showcase_query = urllib.parse.urlencode(
        {
            "glb": relative(glb) or "",
            "thumb": relative(preview) or "",
            "name": case_dir.name,
        }
    )
    result = {
        "case_dir": relative(case_dir),
        "original": relative(original),
        "rectified": relative(analysis_dir / "rectified.png") if (analysis_dir / "rectified.png").exists() else None,
        "mask": relative(analysis_dir / "mask.png") if (analysis_dir / "mask.png").exists() else None,
        "skeleton": relative(analysis_dir / "skeleton.png") if (analysis_dir / "skeleton.png").exists() else None,
        "overlay": relative(analysis_dir / "graph_overlay.png") if (analysis_dir / "graph_overlay.png").exists() else None,
        "schema": relative(analysis_dir / "lattice_schema.json") if (analysis_dir / "lattice_schema.json").exists() else None,
        "report": relative(analysis_dir / "analysis_report.json") if (analysis_dir / "analysis_report.json").exists() else None,
        "clean_mask": relative(vector_dir / "clean_mask.png") if (vector_dir / "clean_mask.png").exists() else None,
        "silhouette_svg": relative(vector_dir / "lattice_contours.svg") if (vector_dir / "lattice_contours.svg").exists() else None,
        "contours": relative(vector_dir / "contour_paths.json") if (vector_dir / "contour_paths.json").exists() else None,
        "blend": relative(blend) if blend.exists() else None,
        "glb": relative(glb) if glb.exists() else None,
        "front_preview": relative(model_dir / "front_render.png") if (model_dir / "front_render.png").exists() else None,
        "perspective_preview": relative(preview) if preview.exists() else None,
        "geometry_report": relative(quality_dir / "geometry_report.json") if (quality_dir / "geometry_report.json").exists() else None,
        "glb_validation": relative(quality_dir / "glb_validation.json") if (quality_dir / "glb_validation.json").exists() else None,
        "showcase_url": f"model_showcase.html?{showcase_query}" if glb.exists() else None,
        "manifest": relative(case_dir / "workflow_manifest.json") if (case_dir / "workflow_manifest.json").exists() else None,
    }
    return result


def find_blender_executable() -> Path:
    candidates = [
        Path("/Applications/Blender.app/Contents/MacOS/Blender"),
        Path("/Applications/Blender 5.2.app/Contents/MacOS/Blender"),
        Path("/Applications/Blender 4.5.app/Contents/MacOS/Blender"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    found = shutil.which("blender")
    if found:
        return Path(found)
    raise FileNotFoundError("未找到 Blender。请先安装 Blender，或将 Blender 放在“应用程序”目录。")


def mask_runs_to_svg(runs: list[dict[str, Any]], width: int, height: int) -> str:
    rects: list[str] = []
    for item in runs:
        try:
            y = int(item["y"])
            x0 = int(item["x0"])
            x1 = int(item["x1"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("轮廓游程数据无效") from exc
        if not (0 <= y < height and 0 <= x0 <= x1 < width):
            raise ValueError("轮廓游程超出图片边界")
        rects.append(f'<rect x="{x0}" y="{y}" width="{x1 - x0 + 1}" height="1"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}"><g fill="#ffffff">'
        + "".join(rects)
        + "</g></svg>"
    )


def update_lattice_manifest(case_dir: Path, model_status: str, reason: str = "") -> dict[str, Any]:
    manifest_path = case_dir / "workflow_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"stages": []}
    for stage in manifest.get("stages", []):
        if stage.get("name") == "三维模型生成":
            stage["status"] = model_status
            if reason:
                stage["reason"] = reason
            else:
                stage.pop("reason", None)
    manifest["workflow"] = "lattice_image_to_3d_v2"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def generate_lattice_case(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    case_id = clean_case_id(case_id)
    case_dir = RUNS / case_id
    schema_path = case_dir / "analysis" / "lattice_schema.json"
    if not schema_path.is_file():
        raise FileNotFoundError("请先完成并保存图片分析")
    if payload.get("confirmed") is not True:
        raise ValueError("生成前必须确认分割结果")
    clean_mask_value = payload.get("clean_mask")
    runs = payload.get("runs")
    width = int(payload.get("width") or 0)
    height = int(payload.get("height") or 0)
    if not isinstance(clean_mask_value, str):
        raise ValueError("缺少确认后的分割图")
    if not isinstance(runs, list) or not runs:
        raise ValueError("确认后的实体轮廓为空")
    if width < 2 or height < 2 or width * height > 2_000_000:
        raise ValueError("确认后的分割图尺寸无效")

    vector_dir = case_dir / "vector"
    quality_dir = case_dir / "quality"
    vector_dir.mkdir(parents=True, exist_ok=True)
    quality_dir.mkdir(parents=True, exist_ok=True)
    mask_data, _ = decode_image_data_url(clean_mask_value)
    (vector_dir / "clean_mask.png").write_bytes(mask_data)
    contour_payload = {
        "representation": "row_run_vectorization_v1",
        "foreground": "white",
        "width": width,
        "height": height,
        "runs": runs,
        "confirmed_by_user": True,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (vector_dir / "contour_paths.json").write_text(json.dumps(contour_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (vector_dir / "lattice_contours.svg").write_text(mask_runs_to_svg(runs, width, height), encoding="utf-8")

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema.setdefault("analysis", {})["segmentation_confirmed"] = True
    schema["analysis"]["confirmed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    schema["generation"] = {
        "route": "silhouette_extrusion",
        "representation": "2.5D",
        "input": "vector/clean_mask.png",
        "generator": "generate_lattice_model.py",
    }
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    update_lattice_manifest(case_dir, "running")

    blender = find_blender_executable()
    generator = ROOT / "generate_lattice_model.py"
    generation = subprocess.run(
        [str(blender), "--background", "--python", str(generator), "--", "--case-dir", str(case_dir)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    (quality_dir / "blender_generation_stdout.log").write_text(generation.stdout, encoding="utf-8")
    (quality_dir / "blender_generation_stderr.log").write_text(generation.stderr, encoding="utf-8")
    glb_path = case_dir / "model" / "lattice_window.glb"
    blend_path = case_dir / "model" / "lattice_window.blend"
    geometry_path = quality_dir / "geometry_report.json"
    if generation.returncode != 0 or not glb_path.is_file() or not blend_path.is_file() or not geometry_path.is_file():
        reason = (generation.stderr or generation.stdout or "Blender 生成失败")[-2500:]
        update_lattice_manifest(case_dir, "failed", reason)
        raise RuntimeError("Blender 生成失败，请查看生成日志。" + reason[-500:])

    frame = schema.get("frame", {})
    bars = schema.get("bars", {})
    expected = [float(frame["width_mm"]) / 1000.0, float(bars["depth_mm"]) / 1000.0, float(frame["height_mm"]) / 1000.0]
    validation_path = quality_dir / "glb_validation.json"
    validator = ROOT / "validate_lattice_glb.py"
    validation = subprocess.run(
        [
            str(blender), "--background", "--python", str(validator), "--",
            "--glb", str(glb_path), "--output", str(validation_path),
            "--expected", *(str(value) for value in expected),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    (quality_dir / "glb_validation_stdout.log").write_text(validation.stdout, encoding="utf-8")
    (quality_dir / "glb_validation_stderr.log").write_text(validation.stderr, encoding="utf-8")
    validation_report = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.is_file() else None
    if validation.returncode != 0 or not validation_report or not validation_report.get("passed"):
        reason = (validation.stderr or validation.stdout or "GLB 校验失败")[-2500:]
        update_lattice_manifest(case_dir, "failed", reason)
        raise RuntimeError("GLB 已生成，但独立重导入校验未通过。" + reason[-500:])

    manifest = update_lattice_manifest(case_dir, "complete")
    return {
        "status": "complete",
        "case_id": case_id,
        "artifacts": lattice_artifacts(case_dir),
        "manifest": manifest,
        "validation": validation_report,
    }


def save_lattice_case(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist a browser-side lattice analysis without requiring image libraries."""
    case_id = clean_case_id(str(payload.get("case_id") or "lattice_case"))
    schema = payload.get("schema")
    images = payload.get("images")
    if not isinstance(schema, dict):
        raise ValueError("schema is required")
    if not isinstance(images, dict):
        raise ValueError("images are required")
    required_images = ("original", "rectified", "mask", "skeleton", "overlay")
    missing = [name for name in required_images if not isinstance(images.get(name), str)]
    if missing:
        raise ValueError("缺少分析图片：" + ", ".join(missing))

    archive_case_dir(case_id)
    case_dir = RUNS / case_id
    source_dir = case_dir / "source"
    analysis_dir = case_dir / "analysis"
    source_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    original_data, original_ext = decode_image_data_url(images["original"])
    (source_dir / f"original{original_ext}").write_bytes(original_data)
    for name, filename in {
        "rectified": "rectified.png",
        "mask": "mask.png",
        "skeleton": "skeleton.png",
        "overlay": "graph_overlay.png",
    }.items():
        data, _ = decode_image_data_url(images[name])
        (analysis_dir / filename).write_bytes(data)

    source_info = {
        "title": str(payload.get("title") or "").strip(),
        "source_url": str(payload.get("source_url") or "").strip(),
        "original_filename": str(payload.get("original_filename") or "").strip(),
        "input_mode": "browser_upload",
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (source_dir / "source_info.json").write_text(json.dumps(source_info, ensure_ascii=False, indent=2), encoding="utf-8")
    (analysis_dir / "lattice_schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "case_id": case_id,
        "status": "analysis_complete",
        "frame_width_mm": schema.get("frame", {}).get("width_mm"),
        "frame_height_mm": schema.get("frame", {}).get("height_mm"),
        "node_count": len(schema.get("nodes", [])),
        "edge_count": len(schema.get("edges", [])),
        "confidence": schema.get("confidence"),
        "estimated_fields": schema.get("estimated_fields", []),
        "next_stage": "deterministic_3d_generation",
    }
    (analysis_dir / "analysis_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "workflow": "lattice_image_analysis_v1",
        "case_id": case_id,
        "stages": [
            {"name": "图片输入与来源记录", "status": "complete"},
            {"name": "窗框四角与真实尺度", "status": "complete"},
            {"name": "透视矫正", "status": "complete"},
            {"name": "纹样分割与骨架提取", "status": "complete"},
            {"name": "节点连线结构化", "status": "complete"},
            {"name": "三维模型生成", "status": "pending"},
            {"name": "建筑构件装配验证", "status": "pending"},
        ],
    }
    (case_dir / "workflow_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": "complete",
        "case_id": case_id,
        "artifacts": lattice_artifacts(case_dir),
        "report": report,
        "manifest": manifest,
    }


def research_has_evidence(case_dir: Path) -> bool:
    path = case_dir / "research.json"
    if not path.exists():
        return False
    try:
        research = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return bool(research.get("sources")) or any(item.get("status") == "passed" and item.get("text") for item in research.get("pages", []))


def infer_progress(case_dir: Path) -> list[dict[str, str]]:
    checks = [
        ("文本需求", case_dir.exists()),
        ("自动调研资料包", research_has_evidence(case_dir)),
        ("高质量建模提示词", (case_dir / "skill_prompt.md").exists()),
        ("Blender 建模代码", (case_dir / "generated_blender_scene.py").exists()),
        ("Blender 生成模型", bool(list((case_dir / "model_output").glob("*.glb")))),
        ("GLB 模型校验", (case_dir / "glb_validation.json").exists()),
    ]
    return [{"name": name, "status": "complete" if ok else "pending"} for name, ok in checks]


def read_manifest(case_dir: Path) -> dict[str, Any] | None:
    path = case_dir / "workflow_manifest.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def artifacts(case_dir: Path, case_id: str) -> dict[str, Any]:
    glb = first_file("model_output/*.glb", case_dir)
    preview = first_file("model_output/*preview*.png", case_dir) or first_file("model_output/*.png", case_dir)
    blend = first_file("model_output/*.blend", case_dir)
    glb_rel = relative(glb)
    preview_rel = relative(preview)
    query = urllib.parse.urlencode(
        {
            "glb": glb_rel or "",
            "thumb": preview_rel or "",
            "name": case_id,
        }
    )
    return {
        "case_dir": relative(case_dir),
        "glb": glb_rel,
        "blend": relative(blend),
        "preview": preview_rel,
        "manifest": relative(case_dir / "workflow_manifest.json") if (case_dir / "workflow_manifest.json").exists() else None,
        "validation": relative(case_dir / "glb_validation.json") if (case_dir / "glb_validation.json").exists() else None,
        "showcase_url": f"model_showcase.html?{query}" if glb_rel else None,
    }


def job_payload(job: dict[str, Any]) -> dict[str, Any]:
    case_dir = RUNS / job["case_id"]
    manifest = read_manifest(case_dir)
    progress = infer_progress(case_dir)
    artifact_payload = artifacts(case_dir, job["case_id"])
    status = job["status"]
    error = job.get("error")
    manifest_failed = any(item.get("status") == "failed" for item in (manifest or {}).get("stages", []))
    if artifact_payload.get("glb") and artifact_payload.get("validation") and not manifest_failed:
        status = "complete"
        error = None
    payload = {
        "id": job["id"],
        "case_id": job["case_id"],
        "question": job["question"],
        "module": job["module"],
        "status": status,
        "started_at": job["started_at"],
        "ended_at": job.get("ended_at"),
        "returncode": job.get("returncode"),
        "error": error,
        "progress": progress,
        "artifacts": artifact_payload,
        "manifest": manifest,
    }
    return payload


def run_job(job: dict[str, Any]) -> None:
    case_dir = RUNS / job["case_id"]
    case_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(ROOT / "run_scene_workflow.py"),
        "--question",
        job["question"],
        "--case-id",
        job["case_id"],
        "--module",
        job["module"],
    ]
    for ref in job["references"]:
        cmd.extend(["--reference", ref])
    job["command"] = cmd
    try:
        completed = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=7200,
        )
        (case_dir / "workflow_server_stdout.log").write_text(completed.stdout, encoding="utf-8")
        (case_dir / "workflow_server_stderr.log").write_text(completed.stderr, encoding="utf-8")
        job["returncode"] = completed.returncode
        manifest = read_manifest(case_dir) or {}
        statuses = {item.get("name"): item.get("status") for item in manifest.get("stages", [])}
        expected = statuses.get("blender_generation") == "complete" and statuses.get("glb_validation") == "complete"
        job["status"] = "complete" if completed.returncode == 0 and expected else "failed"
        if job["status"] == "failed" and not job.get("error"):
            failed = next((item for item in manifest.get("stages", []) if item.get("status") == "failed"), None)
            blocked = next((item for item in manifest.get("stages", []) if item.get("status") in {"model_required", "pending"}), None)
            item = failed or blocked or {}
            if item:
                job["error"] = f"{item.get('name')}: {item.get('reason', item.get('status'))}"
            else:
                job["error"] = "Workflow ended before Blender generation and GLB validation both completed."
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
    finally:
        job["ended_at"] = time.time()


class Handler(SimpleHTTPRequestHandler):
    server_version = "TextTo3DWorkflow/1.0"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file_bytes(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self.send_json({"error": "file not found"}, 404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_raw_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            raise ValueError("request body is required")
        if length > MAX_REQUEST_BYTES:
            raise ValueError("request body exceeds 40 MB")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json({"ok": True})
            return
        if parsed.path == "/api/segmentation-methods/status":
            try:
                from segmentation_methods import segmentation_runtime_status
                self.send_json(segmentation_runtime_status())
            except Exception as exc:
                self.send_json({"sam_ready": False, "c_rule_ready": False, "error": str(exc)}, 503)
            return
        if parsed.path in {"/api/ground-truth/cases", "/api/lattice-dataset/cases"}:
            if parsed.path == "/api/ground-truth/cases":
                cases = imported_ground_truth_cases()
                self.send_json({"cases": cases, "count": len(cases), "mode": "drag_drop_annotation_folder", "ground_truth_count": len(cases)})
                return
            try:
                records = read_dataset_records()
            except Exception as exc:
                self.send_json({"error": str(exc)}, 404)
                return
            selection: dict[str, Any] = {}
            if GROUND_TRUTH_SELECTION.is_file():
                selection = json.loads(GROUND_TRUTH_SELECTION.read_text(encoding="utf-8"))
            ground_truth_ids = {str(case_id) for case_id in selection.get("case_ids", [])}
            mode = "full_frozen_dataset_5x6"
            cases = dataset_cases(records, ground_truth_ids)
            self.send_json({"cases": cases, "count": len(cases), "mode": mode, "ground_truth_count": len(ground_truth_ids)})
            return
        dataset_asset = re.fullmatch(r"/api/lattice-dataset/cases/([^/]+)/source", parsed.path)
        if dataset_asset:
            case_id = clean_case_id(urllib.parse.unquote(dataset_asset.group(1)))
            source_path = dataset_source_path(case_id)
            self.send_file_bytes(source_path, mimetypes.guess_type(source_path.name)[0] or "image/png")
            return
        ground_truth_asset = re.fullmatch(r"/api/ground-truth/cases/([^/]+)/(source|mask)", parsed.path)
        if ground_truth_asset:
            case_id = clean_case_id(urllib.parse.unquote(ground_truth_asset.group(1)))
            case_dir = ground_truth_case_dir(case_id)
            if ground_truth_asset.group(2) == "source":
                source_path = first_file("source.*", case_dir)
                if source_path is None:
                    self.send_json({"error": "人工真值原图不存在"}, 404)
                else:
                    self.send_file_bytes(source_path, mimetypes.guess_type(source_path.name)[0] or "image/png")
            else:
                mask_path = case_dir / "manual_mask.png"
                blank_path = case_dir / "manual_mask_blank.png"
                if mask_path.is_file() or blank_path.is_file():
                    self.send_file_bytes(mask_path if mask_path.is_file() else blank_path, "image/png")
                else:
                    self.send_json({"error": "尚未创建人工Mask"}, 404)
            return
        csam_handoff_asset = re.fullmatch(r"/api/csam-handoffs/([^/]+)/(source|mask)", parsed.path)
        if csam_handoff_asset:
            handoff_id = clean_case_id(urllib.parse.unquote(csam_handoff_asset.group(1)))
            handoff_dir = CSAM_HANDOFFS / handoff_id
            if csam_handoff_asset.group(2) == "source":
                source_path = first_file("source.*", handoff_dir)
                if source_path is None:
                    self.send_json({"error": "C-SAM交接原图不存在"}, 404)
                else:
                    self.send_file_bytes(source_path, mimetypes.guess_type(source_path.name)[0] or "image/png")
            else:
                self.send_file_bytes(handoff_dir / "c6_mask.png", "image/png")
            return
        csam_handoff = re.fullmatch(r"/api/csam-handoffs/([^/]+)", parsed.path)
        if csam_handoff:
            handoff_id = clean_case_id(urllib.parse.unquote(csam_handoff.group(1)))
            handoff_dir = CSAM_HANDOFFS / handoff_id
            metadata_path = handoff_dir / "handoff.json"
            if not metadata_path.is_file():
                self.send_json({"error": "C-SAM交接记录不存在"}, 404)
                return
            self.send_json({
                "status": "complete",
                "metadata": json.loads(metadata_path.read_text(encoding="utf-8")),
                "source_url": f"/api/csam-handoffs/{urllib.parse.quote(handoff_id)}/source",
                "mask_url": f"/api/csam-handoffs/{urllib.parse.quote(handoff_id)}/mask",
            })
            return
        if parsed.path.startswith("/api/workflows/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            job = JOBS.get(job_id)
            if not job:
                self.send_json({"error": "job not found"}, 404)
                return
            self.send_json(job_payload(job))
            return
        if parsed.path.startswith("/api/lattice-cases/"):
            case_id = clean_case_id(parsed.path.rsplit("/", 1)[-1])
            case_dir = RUNS / case_id
            if not case_dir.exists():
                self.send_json({"error": "lattice case not found"}, 404)
                return
            report_path = case_dir / "analysis" / "analysis_report.json"
            manifest_path = case_dir / "workflow_manifest.json"
            report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
            self.send_json({"status": "complete", "case_id": case_id, "artifacts": lattice_artifacts(case_dir), "report": report, "manifest": manifest})
            return
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/segmentation-methods/run":
            try:
                from segmentation_methods import run_segmentation_method
                payload = self.read_json()
                method = str(payload.get("method") or "")
                case_id = clean_case_id(str(payload.get("case_id") or "segmentation_case"))
                image_value = payload.get("image")
                if not isinstance(image_value, str):
                    raise ValueError("缺少待分割图片")
                image_data, _ = decode_image_data_url(image_value)
                prompt = payload.get("prompt") if isinstance(payload.get("prompt"), dict) else {}
                self.send_json(run_segmentation_method(method, case_id, image_data, prompt), 201)
            except Exception as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if parsed.path == "/api/csam-handoffs":
            try:
                self.send_json(save_csam_handoff(self.read_json()), 201)
            except Exception as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if parsed.path == "/api/ground-truth/import":
            try:
                self.send_json(import_ground_truth_image(self.read_json()), 201)
            except Exception as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        ground_truth_save = re.fullmatch(r"/api/ground-truth/cases/([^/]+)", parsed.path)
        if ground_truth_save:
            try:
                case_id = clean_case_id(urllib.parse.unquote(ground_truth_save.group(1)))
                case_dir = ground_truth_case_dir(case_id)
                if not case_dir.is_dir():
                    raise FileNotFoundError("人工真值案例不存在")
                payload = self.read_json()
                mask_value = payload.get("mask")
                if not isinstance(mask_value, str):
                    raise ValueError("缺少人工Mask")
                mask_data, _ = decode_image_data_url(mask_value)
                (case_dir / "manual_mask.png").write_bytes(mask_data)
                status_payload = {
                    "case_id": case_id,
                    "status": "annotation_complete_pending_second_review" if payload.get("submit_for_review") else "manual_annotation_draft",
                    "is_ground_truth": False,
                    "annotator": str(payload.get("annotator") or "").strip(),
                    "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "second_review_required": True,
                    "source_sha256": json.loads((case_dir / "status.json").read_text(encoding="utf-8")).get("source_sha256") if (case_dir / "status.json").is_file() else None,
                }
                (case_dir / "status.json").write_text(json.dumps(status_payload, ensure_ascii=False, indent=2), encoding="utf-8")
                self.send_json(status_payload, 201)
            except Exception as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        lattice_generate_match = re.fullmatch(r"/api/lattice-cases/([^/]+)/generate", parsed.path)
        if lattice_generate_match:
            try:
                payload = self.read_json()
                self.send_json(generate_lattice_case(urllib.parse.unquote(lattice_generate_match.group(1)), payload), 201)
            except Exception as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if parsed.path == "/api/lattice-cases":
            try:
                self.send_json(save_lattice_case(self.read_json()), 201)
            except Exception as exc:
                self.send_json({"error": str(exc)}, 400)
            return
        if parsed.path != "/api/workflows":
            self.send_json({"error": "not found"}, 404)
            return
        try:
            payload = self.read_json()
            question = str(payload.get("question", "")).strip()
            if not question:
                self.send_json({"error": "question is required"}, 400)
                return
            module = str(payload.get("module", "exterior")).strip()
            if module not in {"exterior", "interior"}:
                self.send_json({"error": "module must be exterior or interior"}, 400)
                return
            case_id = clean_case_id(str(payload.get("case_id") or ""))
            references = [str(item).strip() for item in payload.get("references", []) if str(item).strip()]
        except Exception as exc:
            self.send_json({"error": str(exc)}, 400)
            return
        archive_case_dir(case_id)
        job_id = f"{case_id}_{int(time.time())}"
        job = {
            "id": job_id,
            "case_id": case_id,
            "question": question,
            "module": module,
            "references": references,
            "status": "running",
            "started_at": time.time(),
        }
        JOBS[job_id] = job
        threading.Thread(target=run_job, args=(job,), daemon=True).start()
        self.send_json(job_payload(job), 202)


def main() -> None:
    mimetypes.add_type("model/gltf-binary", ".glb")
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Text to 3D workflow server: http://{args.host}:{args.port}/workflow_studio.html", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
