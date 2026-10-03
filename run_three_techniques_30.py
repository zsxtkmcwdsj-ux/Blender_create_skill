from __future__ import annotations

import csv
import json
import shutil
import time
from pathlib import Path
from typing import Any

from segmentation_methods import EXPERIMENT_ROOT, run_segmentation_method


DATA_ROOT = EXPERIMENT_ROOT / "01_冻结数据集/01_统一工作分辨率_30张"
MANIFEST = EXPERIMENT_ROOT / "00_实验设计/dataset_manifest.json"
A_ROOT = EXPERIMENT_ROOT / "04_方法A_传统图像处理_30张"

B_ROOT = EXPERIMENT_ROOT / "06_开放词汇SAM2基础分割_30张"
C_ROOT = EXPERIMENT_ROOT / "08_障碍感知与拓扑反馈窗棂分割_30张"

UNIFIED_ROOT = EXPERIMENT_ROOT / "09_三技术统一测试集_30张"
UNIFIED_INPUT = UNIFIED_ROOT / "00_统一输入"
UNIFIED_A = UNIFIED_ROOT / "01_传统阈值与形态学"
UNIFIED_B = UNIFIED_ROOT / "02_开放词汇SAM2基础分割"
UNIFIED_C = UNIFIED_ROOT / "03_障碍感知与拓扑反馈窗棂分割"
UNIFIED_SUMMARY = UNIFIED_ROOT / "04_统一汇总"

B_REQUIRED = ("source.png", "mask.png", "overlay.png", "run.json")
C_REQUIRED = (
    "source.png",
    "c0_mask.png",
    "c0_overlay.png",
    "c1_mask.png",
    "c1_overlay.png",
    "c2_mask.png",
    "c2_overlay.png",
    "c3_mask.png",
    "c3_overlay.png",
    "c4_mask.png",
    "c4_overlay.png",
    "c5_mask.png",
    "c5_overlay.png",
    "c6_mask.png",
    "c6_overlay.png",
    "obstacle_mask.png",
    "observed_mask.png",
    "inferred_mask.png",
    "confidence_map.png",
    "skeleton.png",
    "topology.json",
    "run.json",
)


def valid_dir(path: Path, required: tuple[str, ...]) -> bool:
    return path.is_dir() and all((path / name).is_file() for name in required)


def latest_valid(roots: list[Path], case_id: str, required: tuple[str, ...]) -> Path | None:
    candidates: list[Path] = []
    for root in roots:
        case_dir = root / case_id
        if not case_dir.is_dir():
            continue
        candidates.extend(path for path in case_dir.iterdir() if valid_dir(path, required))
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0] if candidates else None


def copy_files(source_dir: Path, target_dir: Path, names: tuple[str, ...]) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy2(source_dir / name, target_dir / name)


def mirror_to_canonical(source_dir: Path, canonical_root: Path, case_id: str, required: tuple[str, ...]) -> Path:
    """把旧批次的有效结果无损归档到新的技术名称目录。"""
    try:
        source_dir.relative_to(canonical_root)
        return source_dir
    except ValueError:
        pass
    target_dir = canonical_root / case_id / source_dir.name
    if not valid_dir(target_dir, required):
        copy_files(source_dir, target_dir, required)
    return target_dir


def derive_b_from_c(case_id: str, c_dir: Path) -> Path:
    c_meta = json.loads((c_dir / "run.json").read_text(encoding="utf-8"))
    c0_meta = dict(c_meta["stages"]["C0"])
    metrics = c0_meta.pop("metrics", {})
    c0_meta.pop("stage_duration_seconds", None)
    c0_meta.update(
        {
            "case_id": case_id,
            "image_width": c_meta["image_width"],
            "image_height": c_meta["image_height"],
            "foreground_coverage": metrics.get("foreground_coverage"),
            "source_sha256": c_meta["source_sha256"],
            "duration_seconds": c_meta["stages"]["C0"].get("stage_duration_seconds"),
            "saved_at": c_meta["saved_at"],
            "predicted_iou": c0_meta.get("sam2", {}).get("predicted_iou"),
            "shared_inference_with": "障碍感知与拓扑反馈窗棂分割 C0",
            "fixed_prompt_protocol": "open-vocabulary text ensemble; automatic box; zero clicks; zero brush",
        }
    )
    run_id = c_dir.name
    output = B_ROOT / case_id / run_id
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(c_dir / "source.png", output / "source.png")
    shutil.copy2(c_dir / "c0_mask.png", output / "mask.png")
    shutil.copy2(c_dir / "c0_overlay.png", output / "overlay.png")
    (output / "run.json").write_text(json.dumps(c0_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def a_paths(case_id: str) -> dict[str, Path]:
    case_dir = A_ROOT / case_id
    paths = {
        "source.png": case_dir / "input/source.png",
        "mask.png": case_dir / "vector/clean_mask.png",
        "centerline.png": case_dir / "vector/centerline.png",
        "overlay.png": case_dir / "quality/process_overlay.png",
        "parameters.json": case_dir / "analysis/parameters.json",
        "status.json": case_dir / "quality/status.json",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"{case_id} 的传统阈值与形态学结果不完整：{', '.join(missing)}")
    return paths


def consolidate_case(case_id: str, source_path: Path, a_result: dict[str, Path], b_dir: Path, c_dir: Path) -> None:
    UNIFIED_INPUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, UNIFIED_INPUT / f"{case_id}.png")

    a_target = UNIFIED_A / case_id
    a_target.mkdir(parents=True, exist_ok=True)
    for name, path in a_result.items():
        shutil.copy2(path, a_target / name)
    copy_files(b_dir, UNIFIED_B / case_id, B_REQUIRED)
    copy_files(c_dir, UNIFIED_C / case_id, C_REQUIRED)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = {record["case_id"]: record for record in manifest["records"]}
    case_ids = sorted(records)
    if len(case_ids) != 30:
        raise RuntimeError(f"冻结测试集应为30张，实际为{len(case_ids)}张")

    for path in (B_ROOT, C_ROOT, UNIFIED_INPUT, UNIFIED_A, UNIFIED_B, UNIFIED_C, UNIFIED_SUMMARY):
        path.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    for index, case_id in enumerate(case_ids, start=1):
        source_path = DATA_ROOT / f"{case_id}.png"
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        a_result = a_paths(case_id)

        result = run_segmentation_method("c_sam", case_id, source_path.read_bytes(), {})
        c_dir = Path(result["output_dir"])
        if not valid_dir(c_dir, C_REQUIRED):
            raise RuntimeError(f"{case_id} 的新方法输出不完整")
        b_dir = derive_b_from_c(case_id, c_dir)

        a_meta = json.loads(a_result["parameters.json"].read_text(encoding="utf-8"))
        b_meta = json.loads((b_dir / "run.json").read_text(encoding="utf-8"))
        c_meta = json.loads((c_dir / "run.json").read_text(encoding="utf-8"))
        c6 = c_meta["stages"]["C6"]["metrics"]
        consolidate_case(case_id, source_path, a_result, b_dir, c_dir)
        rows.append(
            {
                "case_id": case_id,
                "category": records[case_id]["category"],
                "difficulty": records[case_id]["difficulty"],
                "traditional_cv_status": "complete",
                "traditional_cv_coverage": a_meta["foreground_coverage"],
                "sam_status": "complete",
                "sam_predicted_iou_internal_confidence": b_meta.get("predicted_iou", ""),
                "sam_foreground_coverage": b_meta.get("foreground_coverage", ""),
                "c_sam_status": "complete",
                "c_sam_c6_foreground_coverage": c6["foreground_coverage"],
                "c_sam_c6_connected_components": c6["connected_components"],
                "c_sam_c6_endpoint_pixels": c6["endpoint_pixels"],
                "c_sam_c6_width_cv": c6["width_cv"],
                "ground_truth_metrics": "pending_manual_ground_truth_review",
                "fixed_prompt": "open-vocabulary text ensemble; automatic box; no clicks; no brush",
                "traditional_cv_source": str(A_ROOT / case_id),
                "sam_source": str(b_dir),
                "c_sam_source": str(c_dir),
            }
        )
        print(f"[{index:02d}/30] {case_id}: 三项结果已整合", flush=True)

    csv_path = UNIFIED_SUMMARY / "三技术30张运行状态与结构指标.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    protocol = {
        "dataset": "30 frozen images from dataset_manifest.json",
        "input_resolution": "01_统一工作分辨率_30张; no further per-case tuning",
        "traditional_cv": "grayscale -> Otsu threshold -> morphology -> skeleton",
        "open_vocabulary_sam2": "Grounding DINO text localization -> SAM2.1 raw mask; no clicks, brush or lattice-specific post-processing",
        "obstacle_aware_topology_feedback": "same C0 -> edge refinement -> semantic obstacle competition -> width constraint -> topology feedback -> evidence-constrained completion -> structured output",
        "manual_brush": False,
        "ground_truth_role": "accuracy metrics remain pending until manual masks pass second review",
        "case_count": 30,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (UNIFIED_SUMMARY / "固定测试协议.json").write_text(
        json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    readme = f"""# 三技术统一测试集（30张）

本目录把同一批30张冻结窗棂图片的三条技术路线结果放在一起：

1. `01_传统阈值与形态学`：灰度化、Otsu阈值、形态学清理与骨架提取。
2. `02_开放词汇SAM2基础分割`：Grounding DINO自动定位窗棂，再由SAM2.1输出原始Mask；不使用点击、人工笔刷或窗棂专用修复。
3. `03_障碍感知与拓扑反馈窗棂分割`：与第2项共享C0，继续执行边界增强、障碍竞争、杆件约束、拓扑反馈、遮挡补全与结构化输出，并保留C0—C6消融结果。

三条路线使用相同30张工作图。两条智能路线采用固定英文概念词组、自动语义选框、零点击、零人工笔刷的固定输入协议；未训练或微调模型。

当前可以比较运行成功率、覆盖率和结构指标；IoU、Dice、Precision、Recall须等人工真值完成并通过第二人复核后再计算。SAM的`predicted_iou`只是模型内部置信度，不是对人工真值的真实IoU。

生成耗时：{time.perf_counter() - started:.1f}秒。
"""
    (UNIFIED_ROOT / "README.md").write_text(readme, encoding="utf-8")
    print(f"完成：{UNIFIED_ROOT}")


if __name__ == "__main__":
    main()
