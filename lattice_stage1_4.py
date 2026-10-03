#!/usr/bin/env python3
"""Build the frozen lattice dataset, GT annotation pack, and Method-A baseline.

Ground-truth files are deliberately initialized as blank and marked pending.
Algorithmic masks are stored only under Method A; they are never copied into the
ground-truth directory. This prevents accidental leakage between the baseline and
the reference annotations.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage.morphology import skeletonize


DATASET = Path("/Users/san/Desktop/text to bim/传统窗棂数据集_v3高清重建_20260823")
METADATA = DATASET / "02_元数据与说明/正式高清核心集_v3_元数据.csv"
SOURCE_ROOT = DATASET / "01_核心数据集_30张/01_按建筑学分类"
OUTPUT = Path("/Users/san/Desktop/text to bim/传统窗棂实验_阶段1至4_20260823")
OLD_NINE = Path("/Users/san/Desktop/text to bim/窗棂9案例_人工真值与方法A_20260823")
BLENDER = Path("/Applications/Blender.app/Contents/MacOS/Blender")
GENERATOR = Path("/Users/san/Desktop/Blender_create_skill/generate_lattice_model.py")
VALIDATOR = Path("/Users/san/Desktop/Blender_create_skill/validate_lattice_glb.py")

DETAILED_CASES = {
    "TWV3_P02": "简单",
    "TWV3_U01": "简单",
    "TWV3_A03": "简单",
    "TWV3_G05": "中等",
    "TWV3_U03": "中等",
    "TWV3_A04": "中等",
    "TWV3_P04": "困难",
    "TWV3_A01": "困难",
    "TWV3_T05": "困难",
}

OLD_CASE_IDS = {
    "TWV3_P02": "S01_P02",
    "TWV3_U01": "S02_U01",
    "TWV3_A03": "S03_A03",
    "TWV3_G05": "M01_G05",
    "TWV3_U03": "M02_U03",
    "TWV3_A04": "M03_A04",
    "TWV3_P04": "H01_P04",
    "TWV3_A01": "H02_A01",
    "TWV3_T05": "H03_T05",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--max-side", type=int, default=1280)
    parser.add_argument("--generate-models", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows() -> list[dict[str, str]]:
    with METADATA.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def find_source(filename: str) -> Path:
    matches = list(SOURCE_ROOT.glob(f"*/*{filename}"))
    if len(matches) != 1:
        raise FileNotFoundError(f"无法唯一定位源图片：{filename}，找到 {len(matches)} 个")
    return matches[0]


def load_working(source: Path, max_side: int) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(source, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"无法读取图片：{source}")
    height, width = image.shape[:2]
    scale = min(1.0, max_side / max(width, height))
    if scale < 1.0:
        image = cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
    return image


def write_png(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(f"PNG编码失败：{path}")
    path.write_bytes(encoded.tobytes())


def remove_small(mask: np.ndarray, minimum: int) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), 8)
    result = np.zeros_like(mask)
    for index in range(1, count):
        if int(stats[index, cv2.CC_STAT_AREA]) >= minimum:
            result[labels == index] = 255
    return result


def method_a(image: np.ndarray) -> dict[str, object]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    threshold, dark = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    light = cv2.bitwise_not(dark)
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    def clean(candidate: np.ndarray) -> np.ndarray:
        candidate = cv2.morphologyEx(candidate, cv2.MORPH_OPEN, kernel_open)
        candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, kernel_close)
        minimum = max(30, round(candidate.size * 0.00004))
        return remove_small(candidate, minimum)

    dark_clean, light_clean = clean(dark), clean(light)
    dark_coverage = float(np.mean(dark_clean > 0))
    light_coverage = float(np.mean(light_clean > 0))
    target = 0.28
    if abs(dark_coverage - target) <= abs(light_coverage - target):
        polarity, raw, cleaned, coverage = "dark", dark, dark_clean, dark_coverage
    else:
        polarity, raw, cleaned, coverage = "light", light, light_clean, light_coverage
    skeleton = (skeletonize(cleaned > 0) * 255).astype(np.uint8)
    return {
        "gray": gray,
        "raw": raw,
        "mask": cleaned,
        "skeleton": skeleton,
        "threshold": float(threshold),
        "polarity": polarity,
        "coverage": coverage,
        "dark_coverage": dark_coverage,
        "light_coverage": light_coverage,
    }


def topology_summary(skeleton: np.ndarray) -> tuple[dict[str, object], np.ndarray]:
    binary = skeleton > 0
    padded = np.pad(binary.astype(np.uint8), 1)
    degree = np.zeros_like(binary, dtype=np.uint8)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            degree += padded[1 + dy : 1 + dy + binary.shape[0], 1 + dx : 1 + dx + binary.shape[1]]
    endpoint = binary & (degree == 1)
    junction = binary & (degree >= 3)
    node_mask = (endpoint | junction).astype(np.uint8)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(node_mask, 8)
    nodes = []
    for index in range(1, count):
        area = int(stats[index, cv2.CC_STAT_AREA])
        x, y = centroids[index]
        local_junction = bool(np.any(junction[labels == index]))
        nodes.append({"id": len(nodes), "x": round(float(x), 2), "y": round(float(y), 2), "pixel_count": area, "kind": "junction" if local_junction else "endpoint"})
    components = cv2.connectedComponents(binary.astype(np.uint8), 8)[0] - 1
    summary = {
        "representation": "pixel_skeleton_summary_v1",
        "skeleton_pixels": int(np.count_nonzero(binary)),
        "connected_components": int(components),
        "endpoint_pixel_count": int(np.count_nonzero(endpoint)),
        "junction_pixel_count": int(np.count_nonzero(junction)),
        "clustered_node_count": len(nodes),
        "nodes": nodes,
        "edge_count_status": "待正式人工中心线后计算图边",
    }
    return summary, node_mask


def overlay_image(image: np.ndarray, mask: np.ndarray, skeleton: np.ndarray, nodes: np.ndarray) -> np.ndarray:
    result = image.copy()
    green = np.zeros_like(result)
    green[:, :, 1] = 255
    alpha = (mask > 0).astype(np.float32)[:, :, None] * 0.28
    result = (result * (1 - alpha) + green * alpha).astype(np.uint8)
    result[skeleton > 0] = (220, 230, 30)
    ys, xs = np.where(nodes > 0)
    for x, y in zip(xs, ys):
        cv2.circle(result, (int(x), int(y)), 2, (0, 140, 255), -1)
    return result


def save_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_reference_candidate(case_id: str, target: Path) -> None:
    old_id = OLD_CASE_IDS[case_id]
    source = OLD_NINE / "01_人工真值" / old_id
    candidate = target / "旧版机器预标注候选_不得作为真值"
    if source.exists() and not candidate.exists():
        shutil.copytree(source, candidate)


def create_review_record(case_dir: Path, row: dict[str, str]) -> None:
    content = f"""# 人工真值复核记录｜{row['编号']}

- 纹样：{row['纹样子类']}
- 建筑学分类：{row['建筑学分类']}
- 技术难度：{row['技术难度']}
- 当前状态：**待人工从空白Mask独立描绘**
- 标注原则：只标记照片中可见的窗框和窗棂实体；遮挡区域不得凭空补全。
- 机器预标注：不得直接作为真值；如查看过预标注，必须在记录中声明。

## 必查项

- [ ] 植物、假山、石头、墙面、阴影均未计入窗棂；
- [ ] 窗棂实体边界连续且不包含孔洞背景；
- [ ] 被遮挡区域按“不可见”处理，没有主观补绘；
- [ ] 第二位复核者逐像素检查；
- [ ] 复核完成后将 `status.json` 改为 `approved`。

标注人：__________  日期：__________

复核人：__________  日期：__________

结论：通过 / 修改后通过 / 不通过
"""
    (case_dir / "人工复核记录.md").write_text(content, encoding="utf-8")


def create_contact_sheet(items: list[tuple[str, Path]], output: Path, title: str, columns: int = 5) -> None:
    tile_w, tile_h, margin = 320, 270, 24
    rows = (len(items) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * tile_w + (columns + 1) * margin, rows * tile_h + (rows + 1) * margin + 54), "#f5f7fa")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    draw.text((margin, 18), title, fill="#111827", font=font)
    for index, (label, path) in enumerate(items):
        image = Image.open(path).convert("RGB")
        image.thumbnail((tile_w - 16, tile_h - 54), Image.Resampling.LANCZOS)
        row, col = divmod(index, columns)
        x = margin + col * tile_w + (tile_w - image.width) // 2
        y = margin + 54 + row * tile_h
        canvas.paste(image, (x, y))
        draw.text((margin + col * tile_w + 8, y + tile_h - 42), label, fill="#111827", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=92)


def build_case(row: dict[str, str], output: Path, max_side: int) -> dict[str, object]:
    case_id = row["编号"]
    source = find_source(row["文件名"])
    actual_hash = sha256(source)
    if actual_hash != row["SHA256"]:
        raise ValueError(f"源图片哈希不一致：{case_id}")
    frozen_dir = output / "01_冻结数据集/00_工作图像_30张"
    frozen_source = frozen_dir / row["文件名"]
    frozen_source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, frozen_source)

    working = load_working(source, max_side)
    working_path = output / "01_冻结数据集/01_统一工作分辨率_30张" / f"{case_id}.png"
    write_png(working_path, working)
    height, width = working.shape[:2]

    gt_dir = output / "02_人工真值_待人工复核" / case_id
    gt_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(working_path, gt_dir / "source.png")
    write_png(gt_dir / "manual_mask_blank.png", np.zeros((height, width), dtype=np.uint8))
    save_json(gt_dir / "status.json", {
        "case_id": case_id,
        "status": "pending_manual_annotation",
        "is_ground_truth": False,
        "reason": "正式真值必须由研究者从空白Mask独立描绘并经第二人复核",
        "working_size": [width, height],
        "source_sha256": actual_hash,
    })
    create_review_record(gt_dir, row)

    baseline_dir = output / "04_方法A_传统图像处理_30张" / case_id
    for name in ("input", "analysis", "vector", "model", "quality"):
        (baseline_dir / name).mkdir(parents=True, exist_ok=True)
    shutil.copy2(working_path, baseline_dir / "input/source.png")
    result = method_a(working)
    topology, nodes = topology_summary(result["skeleton"])
    write_png(baseline_dir / "analysis/01_grayscale.png", result["gray"])
    write_png(baseline_dir / "analysis/02_otsu_raw.png", result["raw"])
    write_png(baseline_dir / "analysis/03_morph_clean.png", result["mask"])
    write_png(baseline_dir / "vector/clean_mask.png", result["mask"])
    write_png(baseline_dir / "vector/centerline.png", result["skeleton"])
    write_png(baseline_dir / "quality/process_overlay.png", overlay_image(working, result["mask"], result["skeleton"], nodes))
    save_json(baseline_dir / "analysis/topology_summary.json", topology)
    parameters = {
        "method": "A_traditional_cv_v1",
        "working_resolution": [width, height],
        "grayscale": "OpenCV BGR2GRAY",
        "threshold": "Otsu global",
        "otsu_value": result["threshold"],
        "polarity_selection": "自动选择前景覆盖率最接近0.28的明/暗候选；不使用人工提示",
        "polarity": result["polarity"],
        "opening": "ellipse 3x3",
        "closing": "ellipse 5x5",
        "min_component_px": max(30, round(width * height * 0.00004)),
        "foreground_coverage": round(float(result["coverage"]), 6),
        "manual_roi": False,
        "color_samples": False,
        "background_suppression": False,
        "manual_mask_edit": False,
    }
    save_json(baseline_dir / "analysis/parameters.json", parameters)
    schema = {
        "case_id": f"A_{case_id}",
        "title": row["纹样子类"],
        "difficulty": row["技术难度"],
        "category": row["建筑学分类"],
        "source": {"path": str(source), "sha256": actual_hash},
        "frame": {"width_mm": 1500.0, "height_mm": round(1500.0 * height / width, 2), "scale_status": "EST"},
        "bars": {"depth_mm": 60.0, "width_mm": "derived_from_mask_EST"},
        "analysis": parameters,
    }
    save_json(baseline_dir / "analysis/lattice_schema.json", schema)
    save_json(baseline_dir / "quality/status.json", {
        "case_id": case_id,
        "method": "A",
        "processing": "complete",
        "metric_status": "blocked_until_ground_truth_approved",
        "model_status": "pending",
    })

    if case_id in DETAILED_CASES:
        detail_dir = output / "03_9个代表案例_详细真值待复核" / case_id
        detail_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(working_path, detail_dir / "source.png")
        create_review_record(detail_dir, row)
        copy_reference_candidate(case_id, detail_dir)
        save_json(detail_dir / "requirements.json", {
            "case_id": case_id,
            "difficulty": row["技术难度"],
            "required": ["人工实体Mask", "人工中心线", "人工节点与连接关系", "人工Blender精确模型", "尺度或EST标记", "第二人复核"],
            "status": "pending_manual_review",
            "old_candidate_is_ground_truth": False,
        })

    return {
        "case_id": case_id,
        "filename": row["文件名"],
        "category": row["建筑学分类"],
        "difficulty": row["技术难度"],
        "source_sha256": actual_hash,
        "working_width": width,
        "working_height": height,
        "ground_truth_status": "pending_manual_annotation",
        "method_a_status": "processing_complete_metrics_pending",
        "method_a_coverage": round(float(result["coverage"]), 6),
    }


def generate_model(case_dir: Path) -> tuple[bool, str]:
    command = [str(BLENDER), "--background", "--python", str(GENERATOR), "--", "--case-dir", str(case_dir)]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    (case_dir / "quality/blender_stdout.log").write_text(completed.stdout, encoding="utf-8")
    (case_dir / "quality/blender_stderr.log").write_text(completed.stderr, encoding="utf-8")
    generated = completed.returncode == 0 and (case_dir / "model/lattice_window.glb").exists() and (case_dir / "model/lattice_window.blend").exists()
    if not generated:
        return False, f"generation_failed_returncode_{completed.returncode}"
    schema = json.loads((case_dir / "analysis/lattice_schema.json").read_text(encoding="utf-8"))
    expected = [
        float(schema["frame"]["width_mm"]) / 1000.0,
        float(schema["bars"]["depth_mm"]) / 1000.0,
        float(schema["frame"]["height_mm"]) / 1000.0,
    ]
    validation_output = case_dir / "quality/glb_validation.json"
    validate = subprocess.run(
        [str(BLENDER), "--background", "--python", str(VALIDATOR), "--", "--glb", str(case_dir / "model/lattice_window.glb"), "--output", str(validation_output), "--expected", *(str(value) for value in expected)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    (case_dir / "quality/validation_stdout.log").write_text(validate.stdout, encoding="utf-8")
    (case_dir / "quality/validation_stderr.log").write_text(validate.stderr, encoding="utf-8")
    passed = validate.returncode == 0 and validation_output.exists()
    return passed, "complete_validated" if passed else f"validation_failed_returncode_{validate.returncode}"


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    if output.exists() and args.overwrite:
        backup = output.with_name(output.name + "_backup_" + time.strftime("%H%M%S"))
        shutil.move(str(output), str(backup))
    output.mkdir(parents=True, exist_ok=True)
    rows = read_rows()
    if len(rows) != 30:
        raise ValueError(f"正式数据集应为30张，实际为{len(rows)}张")
    records = [build_case(row, output, args.max_side) for row in rows]
    write_csv(output / "00_实验设计/30张冻结清单与状态.csv", records)
    save_json(output / "00_实验设计/dataset_manifest.json", {
        "name": "传统窗棂实验_阶段1至4",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source_dataset": str(DATASET),
        "sample_count": 30,
        "detailed_case_count": 9,
        "max_working_side": args.max_side,
        "ground_truth_policy": "从空白Mask独立人工描绘；第二人复核前不得用于正式指标",
        "method_a_policy": "无人工ROI、无颜色取样、无背景抑制、无人工修正",
        "records": records,
    })

    model_status = []
    if args.generate_models:
        for record in records:
            case_dir = output / "04_方法A_传统图像处理_30张" / record["case_id"]
            passed, status = generate_model(case_dir)
            model_status.append({"case_id": record["case_id"], "passed": passed, "status": status})
            status_path = case_dir / "quality/status.json"
            payload = json.loads(status_path.read_text(encoding="utf-8"))
            payload["model_status"] = status
            save_json(status_path, payload)
        write_csv(output / "04_方法A_传统图像处理_30张/模型生成状态.csv", model_status)

    frozen_items = [(record["case_id"], output / "01_冻结数据集/01_统一工作分辨率_30张" / f"{record['case_id']}.png") for record in records]
    method_items = [(record["case_id"], output / "04_方法A_传统图像处理_30张" / record["case_id"] / "quality/process_overlay.png") for record in records]
    create_contact_sheet(frozen_items, output / "05_汇总/冻结数据集30张总览.jpg", "冻结数据集｜30张")
    create_contact_sheet(method_items, output / "05_汇总/方法A结果30张总览.jpg", "方法A｜Mask、骨架与节点")

    readme = """# 传统窗棂实验：阶段1—4

## 已完成

1. 冻结30张正式高清图片，并校验源文件SHA256；
2. 为30张建立独立人工真值标注目录、空白Mask和复核记录；
3. 固定简单/中等/困难各3张，共9张详细案例，并保留旧机器候选供参考；
4. 方法A已对30张完成灰度化、Otsu阈值、形态学去噪、骨架及节点摘要；启用模型批处理时同时生成Blend/GLB。

## 科研准入状态

人工真值尚未完成研究者逐像素描绘和第二人复核，因此当前不能计算或引用正式IoU、Dice等论文指标。旧版机器预标注被隔离在“旧版机器预标注候选_不得作为真值”目录，不会进入正式真值。

## 方法A固定设置

- 统一工作图像最长边1280 px；
- 全局Otsu阈值；
- 明暗候选由固定覆盖率规则自动选择；
- 3×3椭圆开运算、5×5椭圆闭运算；
- 不使用人工ROI、颜色提示、背景抑制和人工Mask修正。
"""
    (output / "README.md").write_text(readme, encoding="utf-8")
    print(json.dumps({"output": str(output), "samples": len(records), "models": model_status}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
