from __future__ import annotations

import csv
import json
import statistics
import time
from pathlib import Path

import cv2
import numpy as np

from segmentation_methods import EXPERIMENT_ROOT, run_segmentation_method


SELECTION = EXPERIMENT_ROOT / "00_实验设计/人工真值三类测验_18张.json"
GROUND_TRUTH_ROOT = EXPERIMENT_ROOT / "02_人工真值_待人工复核"
SUMMARY_ROOT = EXPERIMENT_ROOT / "05_汇总"
LONG_CSV = SUMMARY_ROOT / "C-SAM_C0-C6_18张消融实验_长表.csv"
STAGE_CSV = SUMMARY_ROOT / "C-SAM_C0-C6_阶段汇总.csv"
REPORT = SUMMARY_ROOT / "C-SAM_C0-C6_首轮实验报告.md"


def approved_ground_truth(case_id: str) -> np.ndarray | None:
    case_dir = GROUND_TRUTH_ROOT / case_id
    status_path = case_dir / "status.json"
    mask_path = case_dir / "manual_mask.png"
    if not status_path.is_file() or not mask_path.is_file():
        return None
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if status.get("is_ground_truth") is not True or status.get("second_review_required") is True:
        return None
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    return mask > 127 if mask is not None else None


def segmentation_scores(prediction: np.ndarray, truth: np.ndarray) -> dict[str, float]:
    if prediction.shape != truth.shape:
        prediction = cv2.resize(
            prediction.astype(np.uint8),
            (truth.shape[1], truth.shape[0]),
            interpolation=cv2.INTER_NEAREST,
        ) > 0
    intersection = int(np.count_nonzero(prediction & truth))
    union = int(np.count_nonzero(prediction | truth))
    predicted = int(np.count_nonzero(prediction))
    actual = int(np.count_nonzero(truth))
    return {
        "iou": intersection / max(1, union),
        "dice": 2 * intersection / max(1, predicted + actual),
        "precision": intersection / max(1, predicted),
        "recall": intersection / max(1, actual),
    }


def main() -> None:
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    category_by_case = {
        case_id: category
        for category, case_ids in selection["categories"].items()
        for case_id in case_ids
    }
    rows: list[dict[str, object]] = []
    print("开始运行18张图片的C0—C6冻结消融实验。")
    for index, case_id in enumerate(selection["case_ids"], start=1):
        source_path = GROUND_TRUTH_ROOT / case_id / "source.png"
        result = run_segmentation_method(
            "c_sam",
            case_id,
            source_path.read_bytes(),
            {"box": [1, 1, 999999, 999999], "points": [], "labels": []},
        )
        truth = approved_ground_truth(case_id)
        output_dir = Path(result["output_dir"])
        for stage_name, stage in result["metadata"]["stages"].items():
            metrics = stage["metrics"]
            row: dict[str, object] = {
                "case_id": case_id,
                "category": category_by_case[case_id],
                "stage": stage_name,
                "module": stage["module"],
                "foreground_coverage": metrics["foreground_coverage"],
                "connected_components": metrics["connected_components"],
                "skeleton_pixels": metrics["skeleton_pixels"],
                "endpoint_pixels": metrics["endpoint_pixels"],
                "junction_pixels": metrics["junction_pixels"],
                "median_width_pixels": metrics["median_width_pixels"],
                "width_cv": metrics["width_cv"],
                "green_background_overlap": metrics["green_background_overlap"],
                "stage_duration_seconds": stage["stage_duration_seconds"],
                "ground_truth_approved": truth is not None,
                "iou": "",
                "dice": "",
                "precision": "",
                "recall": "",
                "output_dir": str(output_dir),
            }
            if truth is not None:
                stage_mask = cv2.imread(str(output_dir / f"{stage_name.lower()}_mask.png"), cv2.IMREAD_GRAYSCALE) > 127
                row.update({name: round(value, 6) for name, value in segmentation_scores(stage_mask, truth).items()})
            rows.append(row)
        print(f"[{index}/10] {case_id} 完成：{output_dir}")

    SUMMARY_ROOT.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with LONG_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    numeric_fields = [
        "foreground_coverage",
        "connected_components",
        "skeleton_pixels",
        "endpoint_pixels",
        "junction_pixels",
        "median_width_pixels",
        "width_cv",
        "green_background_overlap",
        "stage_duration_seconds",
    ]
    stage_rows: list[dict[str, object]] = []
    for stage_name in [f"C{number}" for number in range(7)]:
        stage_source = [row for row in rows if row["stage"] == stage_name]
        summary: dict[str, object] = {"stage": stage_name, "case_count": len(stage_source)}
        for field in numeric_fields:
            summary[f"mean_{field}"] = round(statistics.mean(float(row[field]) for row in stage_source), 6)
        approved = [row for row in stage_source if row["ground_truth_approved"]]
        summary["approved_ground_truth_count"] = len(approved)
        summary["mean_iou"] = round(statistics.mean(float(row["iou"]) for row in approved), 6) if approved else ""
        summary["mean_dice"] = round(statistics.mean(float(row["dice"]) for row in approved), 6) if approved else ""
        stage_rows.append(summary)
    with STAGE_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(stage_rows[0]))
        writer.writeheader()
        writer.writerows(stage_rows)

    c0 = stage_rows[0]
    c6 = stage_rows[-1]
    endpoint_change = (float(c6["mean_endpoint_pixels"]) - float(c0["mean_endpoint_pixels"])) / max(1.0, float(c0["mean_endpoint_pixels"]))
    green_change = (float(c6["mean_green_background_overlap"]) - float(c0["mean_green_background_overlap"])) / max(1e-6, float(c0["mean_green_background_overlap"]))
    report = f"""# C-SAM C0—C6首轮消融实验报告

生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}

## 实验设置

- 数据：建筑学五类，每类2张，共10张。
- 固定输入：原图、全图粗框、无正负提示点、无人工笔刷。
- 初始分割：Meta SAM ViT-B。
- 方法版本：`c_sam_v1_frozen`。
- C0—C6每一级只增加一个模块，所有Mask、叠加图、参数和结构指标均独立保存。

## 各级定义

1. C0：原始SAM。
2. C1：加入自由ROI与坐标归一化。
3. C2：加入植被、粗糙背景和材质不一致区域排除。
4. C3：加入杆件宽度一致性过滤。
5. C4：加入小连通区域与短枝杈清理。
6. C5：加入有图像支持的近距离断点连接。
7. C6：加入全局连通性、边框保留和拓扑清理，形成完整C-SAM。

## 当前可报告结果

- 10张×7级，共生成{len(rows)}组二维结果。
- C0平均绿色背景重叠率：{float(c0['mean_green_background_overlap']):.4f}。
- C6平均绿色背景重叠率：{float(c6['mean_green_background_overlap']):.4f}，相对变化{green_change * 100:.1f}%。
- C0平均断点像素数：{float(c0['mean_endpoint_pixels']):.1f}。
- C6平均断点像素数：{float(c6['mean_endpoint_pixels']):.1f}，相对变化{endpoint_change * 100:.1f}%。
- C6平均宽度变异系数：{float(c6['mean_width_cv']):.4f}。

## 准确率状态

通过第二人复核的人工真值数量为{int(c6['approved_ground_truth_count'])}/18，因此IoU、Dice、Precision、Recall暂不形成论文结论。待人工Mask复核后重新运行本脚本，汇总表会自动补算这些指标。

## 解释限制

断点数降低和宽度一致性改善只能证明结构被规则化，不能单独证明分割更准确；如果规则过强，也可能删除真实细节。最终必须结合人工真值、逐类可视化和失败案例共同判断。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"长表：{LONG_CSV}")
    print(f"阶段汇总：{STAGE_CSV}")
    print(f"报告：{REPORT}")


if __name__ == "__main__":
    main()
