from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import threading
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image
from skimage.morphology import skeletonize

from open_vocab_models import run_open_vocabulary_sam2, runtime_status as open_vocab_runtime_status


ROOT = Path(__file__).resolve().parent
EXPERIMENT_ROOT = Path("/Users/san/Desktop/text to bim/传统窗棂实验_阶段1至4_20260823")
SAM_CHECKPOINT = ROOT / "models" / "sam_vit_b_01ec64.pth"
SAM_MODEL_TYPE = "vit_b"
SAM_REPOSITORY_COMMIT = "dca509fe793f601edb92606367a655c15ac00fdf"

_sam_predictor: Any = None
_sam_device = "not_loaded"
_sam_lock = threading.Lock()
_sam_checkpoint_sha256: str | None = None


def _sha256_file(path: Path) -> str:
    global _sam_checkpoint_sha256
    if path == SAM_CHECKPOINT and _sam_checkpoint_sha256:
        return _sam_checkpoint_sha256
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    result = digest.hexdigest()
    if path == SAM_CHECKPOINT:
        _sam_checkpoint_sha256 = result
    return result


def _clean_case_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())[:80].strip("_")
    return cleaned or time.strftime("segmentation_%Y%m%d_%H%M%S")


def _read_rgb(image_bytes: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(image_bytes)) as image:
        image = image.convert("RGB")
        if max(image.size) > 1600:
            image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        return np.asarray(image).copy()


def _png_bytes(array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format="PNG")
    return buffer.getvalue()


def _data_url(array: np.ndarray) -> str:
    return "data:image/png;base64," + base64.b64encode(_png_bytes(array)).decode("ascii")


def _overlay(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    result = rgb.astype(np.float32)
    tint = np.array([45, 212, 191], dtype=np.float32)
    selected = mask.astype(bool)
    result[selected] = result[selected] * 0.42 + tint * 0.58
    return np.clip(result, 0, 255).astype(np.uint8)


def _completion_overlay(rgb: np.ndarray, visible: np.ndarray, inferred: np.ndarray) -> np.ndarray:
    """Layered diagnostic: teal is observed material, amber is inferred."""
    result = rgb.astype(np.float32)
    observed = visible.astype(bool)
    bridge = inferred.astype(bool) & ~observed
    result[observed] = result[observed] * 0.46 + np.array([45, 212, 191], dtype=np.float32) * 0.54
    result[bridge] = result[bridge] * 0.30 + np.array([255, 174, 35], dtype=np.float32) * 0.70
    return np.clip(result, 0, 255).astype(np.uint8)


def _obstacle_diagnostic_overlay(
    rgb: np.ndarray,
    visible: np.ndarray,
    interference: np.ndarray,
    occluder: np.ndarray,
) -> np.ndarray:
    """Show that obstacle evidence is actively excluded rather than disappearing.

    Purple denotes plant/rough-background interference, yellow denotes the subset
    admitted as a true occlusion field near an interrupted observed graph, and
    teal denotes retained visible lattice material.
    """
    result = rgb.astype(np.float32)
    rejected = interference.astype(bool) & ~visible.astype(bool)
    admitted = occluder.astype(bool) & ~visible.astype(bool)
    observed = visible.astype(bool)
    result[rejected] = result[rejected] * 0.72 + np.array([190, 75, 220], dtype=np.float32) * 0.28
    result[admitted] = result[admitted] * 0.48 + np.array([255, 214, 64], dtype=np.float32) * 0.52
    result[observed] = result[observed] * 0.46 + np.array([45, 212, 191], dtype=np.float32) * 0.54
    return np.clip(result, 0, 255).astype(np.uint8)


def _mask_png(mask: np.ndarray) -> np.ndarray:
    return np.where(mask, 255, 0).astype(np.uint8)


def _load_sam_predictor() -> tuple[Any, str]:
    global _sam_predictor, _sam_device
    with _sam_lock:
        if _sam_predictor is not None:
            return _sam_predictor, _sam_device
        if not SAM_CHECKPOINT.is_file() or SAM_CHECKPOINT.stat().st_size < 350 * 1024 * 1024:
            raise FileNotFoundError(f"缺少SAM权重：{SAM_CHECKPOINT}")
        import torch
        from segment_anything import SamPredictor, sam_model_registry

        if torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
        model = sam_model_registry[SAM_MODEL_TYPE](checkpoint=str(SAM_CHECKPOINT))
        model.to(device=device)
        model.eval()
        _sam_predictor = SamPredictor(model)
        _sam_device = device
        return _sam_predictor, _sam_device


def _normalize_box(box: Any, width: int, height: int) -> np.ndarray:
    if not isinstance(box, list) or len(box) != 4:
        return np.array([1, 1, width - 2, height - 2], dtype=np.float32)
    x0, y0, x1, y1 = [float(value) for value in box]
    x0, x1 = sorted((max(0.0, min(width - 1.0, x0)), max(0.0, min(width - 1.0, x1))))
    y0, y1 = sorted((max(0.0, min(height - 1.0, y0)), max(0.0, min(height - 1.0, y1))))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return np.array([1, 1, width - 2, height - 2], dtype=np.float32)
    return np.array([x0, y0, x1, y1], dtype=np.float32)


def _normalize_points(points: Any, labels: Any, width: int, height: int) -> tuple[np.ndarray | None, np.ndarray | None]:
    if not isinstance(points, list) or not isinstance(labels, list) or len(points) != len(labels):
        return None, None
    valid_points: list[list[float]] = []
    valid_labels: list[int] = []
    for point, label in zip(points, labels):
        if not isinstance(point, list) or len(point) != 2 or int(label) not in (0, 1):
            continue
        valid_points.append([
            max(0.0, min(width - 1.0, float(point[0]))),
            max(0.0, min(height - 1.0, float(point[1]))),
        ])
        valid_labels.append(int(label))
    if not valid_points:
        return None, None
    return np.asarray(valid_points, dtype=np.float32), np.asarray(valid_labels, dtype=np.int32)


def run_sam_baseline(rgb: np.ndarray, prompt: dict[str, Any] | None = None) -> tuple[np.ndarray, dict[str, Any]]:
    """Method B: fixed zero-shot semantic localization plus raw SAM2.1 segmentation."""
    mask, _obstacle_proposals, metadata = run_open_vocabulary_sam2(rgb)
    metadata["input_protocol"] = "fixed text-prompt ensemble; automatic box; no clicks; no brush"
    metadata["ignored_browser_prompt"] = bool(prompt)
    return mask, metadata


def _remove_small_components(mask: np.ndarray, minimum_area: int) -> tuple[np.ndarray, int]:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    if count <= 1:
        return mask.astype(bool), 0
    component_areas = stats[1:, cv2.CC_STAT_AREA]
    largest = int(component_areas.max(initial=0))
    keep_threshold = max(minimum_area, int(largest * 0.02))
    output = np.zeros(mask.shape, dtype=np.uint8)
    removed = 0
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area >= keep_threshold:
            output[labels == label] = 1
        else:
            removed += 1
    return output.astype(bool), removed


def run_c_rule(rgb: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    """Frozen, automatic rule baseline derived from the current browser method.

    No brush strokes, color samples, background samples, adaptive per-image tuning,
    SAM output, gap repair or topology repair are allowed in this baseline.
    """
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    threshold, dark_raw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    _, light_raw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    red, green, blue = [rgb[:, :, index].astype(np.int16) for index in range(3)]
    green_background = (green > red + 10) & (green > blue + 8) & (green - np.minimum(red, blue) > 16)
    kernel = np.ones((3, 3), dtype=np.uint8)
    minimum_area = max(12, int(rgb.shape[0] * rgb.shape[1] * 0.00012))

    candidates: list[tuple[str, np.ndarray, float, int]] = []
    for polarity, raw in (("dark", dark_raw), ("light", light_raw)):
        candidate = (raw > 0) & ~green_background
        candidate = cv2.morphologyEx(candidate.astype(np.uint8), cv2.MORPH_CLOSE, kernel, iterations=1)
        candidate = cv2.morphologyEx(candidate, cv2.MORPH_OPEN, kernel, iterations=1)
        candidate, removed = _remove_small_components(candidate > 0, minimum_area)
        coverage = float(candidate.mean())
        score = abs(coverage - 0.28) + (1.0 if coverage < 0.025 or coverage > 0.72 else 0.0)
        candidates.append((polarity, candidate, score, removed))
    polarity, mask, _, removed = min(candidates, key=lambda item: item[2])
    metadata = {
        "method": "C-Rule",
        "definition": "Frozen automatic rules from the current web workflow; no SAM and no manual brush",
        "algorithm_version": "c_rule_v1",
        "threshold_method": "Otsu",
        "otsu_threshold": round(float(threshold), 3),
        "polarity_selection": "automatic_fixed_target_coverage",
        "polarity_used": polarity,
        "green_background_suppression": True,
        "morphology": "3x3 close once, 3x3 open once",
        "minimum_component_area": minimum_area,
        "removed_small_components": removed,
        "manual_brush": False,
        "manual_color_samples": False,
        "gap_repair": False,
        "topology_repair": False,
    }
    return mask, metadata


def _kernel(size: int) -> np.ndarray:
    size = max(1, int(size))
    if size % 2 == 0:
        size += 1
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def _skeleton(mask: np.ndarray) -> np.ndarray:
    return skeletonize(mask.astype(bool)).astype(np.uint8)


def _neighbor_count(skeleton: np.ndarray) -> np.ndarray:
    neighbors = cv2.filter2D(skeleton.astype(np.uint8), cv2.CV_16S, np.ones((3, 3), np.uint8))
    return neighbors - skeleton.astype(np.int16)


def _structural_metrics(mask: np.ndarray, rgb: np.ndarray | None = None) -> dict[str, Any]:
    binary = mask.astype(bool)
    skel = _skeleton(binary)
    neighbors = _neighbor_count(skel)
    components = max(0, cv2.connectedComponents(binary.astype(np.uint8), connectivity=8)[0] - 1)
    distance = cv2.distanceTransform(binary.astype(np.uint8), cv2.DIST_L2, 5)
    widths = distance[skel > 0] * 2.0
    result: dict[str, Any] = {
        "foreground_coverage": round(float(binary.mean()), 6),
        "connected_components": int(components),
        "skeleton_pixels": int(skel.sum()),
        "endpoint_pixels": int(np.count_nonzero((skel > 0) & (neighbors == 1))),
        "junction_pixels": int(np.count_nonzero((skel > 0) & (neighbors >= 3))),
        "median_width_pixels": round(float(np.median(widths)), 3) if widths.size else 0.0,
        "width_cv": round(float(np.std(widths) / max(np.mean(widths), 1e-6)), 4) if widths.size else 0.0,
    }
    if rgb is not None:
        red, green, blue = [rgb[:, :, index].astype(np.int16) for index in range(3)]
        vegetation = (green > red + 10) & (green > blue + 8) & (green - np.minimum(red, blue) > 16)
        selected = max(1, int(binary.sum()))
        result["green_background_overlap"] = round(float(np.count_nonzero(binary & vegetation) / selected), 6)
    return result


def _estimate_roi_mask(rgb: np.ndarray, prompt: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    """Estimate a window work region while retaining irregular outlines.

    A user box is accepted as a coarse prompt, never as pixel-level annotation. With a
    full-image box, the largest central structural contour is used when reliable.
    """
    height, width = rgb.shape[:2]
    box = _normalize_box(prompt.get("box"), width, height)
    x0, y0, x1, y1 = [int(round(value)) for value in box]
    box_area = max(1, (x1 - x0) * (y1 - y0))
    full_ratio = box_area / float(width * height)
    roi = np.zeros((height, width), np.uint8)
    roi[max(0, y0):min(height, y1 + 1), max(0, x0):min(width, x1 + 1)] = 1
    source = "prompt_box"
    polygon: list[list[int]] = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]

    if full_ratio > 0.88:
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 35, 110)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, _kernel(max(5, min(height, width) // 90)), iterations=2)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        center = np.array([width / 2.0, height / 2.0])
        best: tuple[float, np.ndarray] | None = None
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < width * height * 0.20:
                continue
            bx, by, bw, bh = cv2.boundingRect(contour)
            if bw < width * 0.42 or bh < height * 0.42:
                continue
            contour_center = np.array([bx + bw / 2.0, by + bh / 2.0])
            center_penalty = float(np.linalg.norm((contour_center - center) / np.array([width, height])))
            score = area / (width * height) - center_penalty * 0.7
            if best is None or score > best[0]:
                best = (score, contour)
        if best is not None:
            hull = cv2.convexHull(best[1])
            candidate = np.zeros_like(roi)
            cv2.fillPoly(candidate, [hull], 1)
            coverage = float(candidate.mean())
            if 0.28 <= coverage <= 0.99:
                roi = candidate
                source = "automatic_irregular_outer_contour"
                epsilon = 0.012 * cv2.arcLength(hull, True)
                approx = cv2.approxPolyDP(hull, epsilon, True).reshape(-1, 2)
                polygon = [[int(x), int(y)] for x, y in approx]

    return roi.astype(bool), {
        "roi_source": source,
        "roi_coverage": round(float(roi.mean()), 6),
        "roi_polygon": polygon,
        "perspective_normalization": "ROI-normalized coordinates; output mapped to source image",
    }


def _background_suppression(rgb: np.ndarray, mask: np.ndarray, roi: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    red, green, blue = [rgb[:, :, index].astype(np.int16) for index in range(3)]
    rgb_green = (green > red + 8) & (green > blue + 6) & (green - np.minimum(red, blue) > 12)
    hsv_green = (hsv[:, :, 0] >= 26) & (hsv[:, :, 0] <= 100) & (hsv[:, :, 1] >= 38)
    vegetation = rgb_green | hsv_green

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    block = max(15, (min(gray.shape) // 18) | 1)
    dark_lines = cv2.adaptiveThreshold(clahe, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block, 4) > 0
    light_lines = cv2.adaptiveThreshold(clahe, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 7) > 0
    edges = cv2.Canny(clahe, 45, 135) > 0
    edge_support = cv2.dilate(edges.astype(np.uint8), _kernel(3), iterations=1) > 0

    # Learn up to three material colours from the visible outer frame. This is an
    # image-internal baseline, not a per-case hand-tuned colour sample.
    band_size = max(5, int(round(min(gray.shape) * 0.035)))
    inner_roi = cv2.erode(roi.astype(np.uint8), _kernel(band_size * 2 + 1), iterations=1) > 0
    frame_band = roi & ~inner_roi
    samples = lab[frame_band & (edge_support | mask) & ~vegetation].reshape(-1, 3).astype(np.float32)
    if len(samples) > 9000:
        samples = samples[np.linspace(0, len(samples) - 1, 9000).astype(int)]
    if len(samples) >= 30:
        cluster_count = min(3, max(1, len(samples) // 400))
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 35, 0.2)
        cv2.setRNGSeed(20260823)
        _, _, centers = cv2.kmeans(samples, cluster_count, None, criteria, 5, cv2.KMEANS_PP_CENTERS)
    else:
        centers = np.asarray([[float(np.median(lab[:, :, channel])) for channel in range(3)]], dtype=np.float32)
    lab_float = lab.astype(np.float32)
    material_distance = np.min(
        np.stack([np.linalg.norm(lab_float - center.reshape(1, 1, 3), axis=2) for center in centers]),
        axis=0,
    )
    distance_limit = max(16.0, min(34.0, float(np.percentile(material_distance[frame_band], 82)) + 8.0)) if np.any(frame_band) else 28.0
    material_likelihood = material_distance <= distance_limit
    neutral_structure = (hsv[:, :, 1] < 48) & edge_support

    # Select the polarity whose line evidence agrees better with the SAM region while
    # avoiding implausibly large filled surfaces.
    candidates = []
    for name, lines in (("dark", dark_lines), ("light", light_lines)):
        candidate = lines & roi & ~vegetation & (material_likelihood | neutral_structure)
        agreement = float(np.count_nonzero(candidate & mask) / max(1, np.count_nonzero(candidate)))
        coverage = float(candidate.mean())
        score = agreement - abs(coverage - 0.22) * 0.55
        candidates.append((score, name, candidate))
    _, polarity, line_evidence = max(candidates, key=lambda item: item[0])

    sam_support = cv2.dilate(mask.astype(np.uint8), _kernel(5), iterations=1) > 0
    structural = line_evidence & (sam_support | edge_support) & (material_likelihood | neutral_structure)
    structural |= mask & edge_support & ~vegetation & roi & material_likelihood
    structural |= frame_band & mask & ~vegetation & material_likelihood
    structural = cv2.morphologyEx(structural.astype(np.uint8), cv2.MORPH_CLOSE, _kernel(3), iterations=1) > 0

    # Very rough stone/wall patches tend to have high local Lab variance but no
    # persistent line support. They are removed only outside the selected line map.
    local_mean = cv2.GaussianBlur(lab.astype(np.float32), (0, 0), 3)
    local_sq = cv2.GaussianBlur((lab.astype(np.float32) ** 2), (0, 0), 3)
    texture = np.sqrt(np.maximum(0.0, (local_sq - local_mean ** 2).mean(axis=2)))
    texture_threshold = float(np.percentile(texture[roi], 88)) if np.any(roi) else float(np.percentile(texture, 88))
    rough_background = (texture > texture_threshold) & ~edge_support
    before = int(mask.sum())
    structural &= ~rough_background
    return structural, {
        "selected_line_polarity": polarity,
        "vegetation_pixels_excluded": int(np.count_nonzero(mask & vegetation)),
        "rough_background_pixels_excluded": int(np.count_nonzero(mask & rough_background)),
        "background_removed_pixels": max(0, before - int(structural.sum())),
        "texture_threshold": round(texture_threshold, 3),
        "material_cluster_centers_lab": [[round(float(value), 2) for value in center] for center in centers],
        "material_distance_limit": round(float(distance_limit), 3),
    }


def _width_filter(mask: np.ndarray, roi: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    binary = mask.astype(np.uint8)
    skel = _skeleton(binary)
    distance = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    radii = distance[skel > 0]
    if radii.size < 8:
        return mask.astype(bool), {"dominant_width_pixels": 0.0, "maximum_width_pixels": 0.0, "wide_core_removed": 0}
    lower = radii[radii <= np.percentile(radii, 72)]
    dominant_radius = max(1.0, float(np.median(lower if lower.size else radii)))
    maximum_radius = max(dominant_radius * 2.8, float(np.percentile(radii, 90)))
    wide_core = distance > maximum_radius
    # Preserve a narrow outer-frame band: it belongs to the architectural object
    # even when it is wider than internal lattice bars.
    erosion_size = max(3, int(round(dominant_radius * 3)) | 1)
    inner_roi = cv2.erode(roi.astype(np.uint8), _kernel(erosion_size), iterations=1) > 0
    removable = wide_core & inner_roi
    result = binary.copy()
    result[removable] = 0
    result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, _kernel(3), iterations=1)
    return result.astype(bool), {
        "dominant_width_pixels": round(dominant_radius * 2.0, 3),
        "maximum_width_pixels": round(maximum_radius * 2.0, 3),
        "wide_core_removed": int(np.count_nonzero(removable)),
    }


def _prune_short_spurs(skeleton: np.ndarray, maximum_length: int) -> tuple[np.ndarray, int]:
    result = skeleton.astype(np.uint8).copy()
    removed_total = 0
    for _ in range(max(1, maximum_length)):
        neighbors = _neighbor_count(result)
        endpoints = (result > 0) & (neighbors <= 1)
        if not np.any(endpoints):
            break
        # Iterative endpoint peeling removes only short terminal branches; pixels
        # belonging to loops and junction cores are untouched.
        removable = endpoints & (neighbors < 3)
        count = int(removable.sum())
        if count == 0:
            break
        result[removable] = 0
        removed_total += count
    return result, removed_total


def _remove_noise_and_spurs(mask: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    minimum_area = max(10, int(mask.size * 0.00010))
    cleaned, removed_components = _remove_small_components(mask, minimum_area)
    skel = _skeleton(cleaned)
    distance = cv2.distanceTransform(cleaned.astype(np.uint8), cv2.DIST_L2, 5)
    widths = distance[skel > 0] * 2.0
    radius = max(1, int(round((float(np.median(widths)) if widths.size else 3.0) / 2.0)))
    spur_length = max(2, min(10, int(round(radius * 1.8))))
    pruned, removed_spur_pixels = _prune_short_spurs(skel, spur_length)
    reconstructed = cv2.dilate(pruned, _kernel(radius * 2 + 1), iterations=1) > 0
    reconstructed &= cv2.dilate(cleaned.astype(np.uint8), _kernel(3), iterations=1) > 0
    return reconstructed, {
        "minimum_component_area": minimum_area,
        "removed_components": int(removed_components),
        "spur_length_limit": spur_length,
        "removed_spur_pixels": int(removed_spur_pixels),
    }


def _line_support_ratio(support: np.ndarray, p0: tuple[int, int], p1: tuple[int, int]) -> float:
    sample = np.zeros(support.shape, np.uint8)
    cv2.line(sample, p0, p1, 1, 1, cv2.LINE_8)
    count = int(sample.sum())
    return float(np.count_nonzero((sample > 0) & support) / max(1, count))


def _connect_gaps(mask: np.ndarray, rgb: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    skel = _skeleton(mask)
    neighbors = _neighbor_count(skel)
    ys, xs = np.where((skel > 0) & (neighbors == 1))
    endpoints = [(int(x), int(y)) for y, x in zip(ys, xs)]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edge_support = cv2.dilate((cv2.Canny(gray, 40, 130) > 0).astype(np.uint8), _kernel(5), iterations=1) > 0
    support = edge_support | (cv2.dilate(mask.astype(np.uint8), _kernel(5), iterations=1) > 0)
    maximum_gap = max(5, int(round(min(mask.shape) * 0.035)))
    used: set[int] = set()
    connections: list[dict[str, Any]] = []
    for index, p0 in enumerate(endpoints):
        if index in used:
            continue
        choices = []
        for other_index in range(index + 1, len(endpoints)):
            if other_index in used:
                continue
            p1 = endpoints[other_index]
            distance = float(np.hypot(p1[0] - p0[0], p1[1] - p0[1]))
            if 2.0 < distance <= maximum_gap:
                ratio = _line_support_ratio(support, p0, p1)
                if ratio >= 0.52:
                    choices.append((distance / max(ratio, 0.01), other_index, p1, distance, ratio))
        if not choices:
            continue
        _, other_index, p1, distance, ratio = min(choices, key=lambda item: item[0])
        cv2.line(skel, p0, p1, 1, 1, cv2.LINE_AA)
        used.update((index, other_index))
        connections.append({"from": list(p0), "to": list(p1), "distance": round(distance, 3), "support": round(ratio, 3)})
    distance_map = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    original_widths = distance_map[_skeleton(mask) > 0] * 2.0
    radius = max(1, int(round((float(np.median(original_widths)) if original_widths.size else 3.0) / 2.0)))
    reconstructed = cv2.dilate(skel, _kernel(radius * 2 + 1), iterations=1) > 0
    reconstructed |= mask
    return reconstructed, {
        "maximum_gap_pixels": maximum_gap,
        "connections_added": len(connections),
        "connections": connections,
    }


def _topology_repair(mask: np.ndarray, roi: np.ndarray, rgb: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    binary = mask.astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    areas = stats[1:, cv2.CC_STAT_AREA] if count > 1 else np.array([], dtype=np.int32)
    largest = int(areas.max(initial=0))
    minimum_area = max(int(mask.size * 0.00016), int(largest * 0.012), 12)
    result = np.zeros_like(binary)
    kept = 0
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        component = labels == label
        touches_roi_boundary = bool(np.any(component & (roi ^ (cv2.erode(roi.astype(np.uint8), _kernel(5), iterations=1) > 0))))
        if area >= minimum_area or touches_roi_boundary:
            result[component] = 1
            kept += 1
    result &= roi.astype(np.uint8)
    red, green, blue = [rgb[:, :, index].astype(np.int16) for index in range(3)]
    vegetation = (green > red + 10) & (green > blue + 8) & (green - np.minimum(red, blue) > 16)
    result[vegetation] = 0
    result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, _kernel(3), iterations=1)
    skel = _skeleton(result)
    pruned, removed_spurs = _prune_short_spurs(skel, max(2, int(round(min(mask.shape) * 0.006))))
    distance = cv2.distanceTransform(result, cv2.DIST_L2, 5)
    widths = distance[skel > 0] * 2.0
    radius = max(1, int(round((float(np.median(widths)) if widths.size else 3.0) / 2.0)))
    repaired = cv2.dilate(pruned, _kernel(radius * 2 + 1), iterations=1) > 0
    repaired &= cv2.dilate(result, _kernel(3), iterations=1) > 0
    return repaired, {
        "minimum_topology_component_area": minimum_area,
        "components_kept": kept,
        "components_removed": max(0, count - 1 - kept),
        "final_spur_pixels_removed": int(removed_spurs),
        "topology_policy": "retain substantial/frame-connected structure; suppress vegetation; prune terminal noise without inventing hidden pattern",
    }


def _edge_guided_refinement(rgb: np.ndarray, initial: np.ndarray, roi: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    """Recover thin lattice boundaries without using labels or per-image tuning."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8)).apply(gray)
    edges = cv2.Canny(clahe, 32, 118) > 0
    edge_band = cv2.dilate(edges.astype(np.uint8), _kernel(3), iterations=1) > 0
    block = max(15, (min(gray.shape) // 22) | 1)
    dark = cv2.adaptiveThreshold(clahe, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block, 5) > 0
    light = cv2.adaptiveThreshold(clahe, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 8) > 0

    boundary = roi ^ (cv2.erode(roi.astype(np.uint8), _kernel(max(5, (min(gray.shape) // 45) | 1)), iterations=1) > 0)
    samples = lab[boundary & edge_band].reshape(-1, 3).astype(np.float32)
    if len(samples) > 6000:
        samples = samples[np.linspace(0, len(samples) - 1, 6000).astype(int)]
    if len(samples) >= 24:
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.25)
        cv2.setRNGSeed(20260825)
        clusters = min(3, max(1, len(samples) // 500))
        _, _, centers = cv2.kmeans(samples, clusters, None, criteria, 4, cv2.KMEANS_PP_CENTERS)
        distances = np.min(
            np.stack([np.linalg.norm(lab.astype(np.float32) - center.reshape(1, 1, 3), axis=2) for center in centers]),
            axis=0,
        )
        threshold = float(np.percentile(distances[boundary], 88)) + 7.0 if np.any(boundary) else 30.0
        material = distances <= max(18.0, min(38.0, threshold))
    else:
        centers = np.asarray([], dtype=np.float32).reshape(0, 3)
        material = np.ones(gray.shape, dtype=bool)

    support = cv2.dilate(initial.astype(np.uint8), _kernel(7), iterations=1) > 0
    candidates = []
    for polarity, line_map in (("dark", dark), ("light", light)):
        candidate = line_map & roi & material & (edge_band | support)
        coverage = float(candidate.mean())
        edge_agreement = float(np.count_nonzero(candidate & edge_band) / max(1, np.count_nonzero(candidate)))
        score = edge_agreement - abs(coverage - 0.20) * 0.7
        candidates.append((score, polarity, candidate))
    _, polarity, refined = max(candidates, key=lambda item: item[0])
    # Painted/stone-grey lattice bars are often brighter and less saturated than
    # foliage behind them. Fill their interiors near persistent edges; wide wall
    # patches are intentionally left for the later width/topology modules.
    neutral_material = (hsv[:, :, 1] <= 82) & (hsv[:, :, 2] >= 48) & (hsv[:, :, 2] <= 246)
    neutral_line = neutral_material & roi & (cv2.dilate(edges.astype(np.uint8), _kernel(9), iterations=1) > 0)
    refined |= neutral_line
    refined |= boundary & edge_band & material
    refined = cv2.morphologyEx(refined.astype(np.uint8), cv2.MORPH_CLOSE, _kernel(3), iterations=1) > 0
    refined, removed = _remove_small_components(refined, max(8, int(refined.size * 0.00006)))
    return refined, {
        "selected_polarity": polarity,
        "edge_pixels": int(edges.sum()),
        "material_centers_lab": [[round(float(v), 2) for v in center] for center in centers],
        "small_components_removed": int(removed),
        "policy": "automatic edge/material refinement inside the semantic window region; no manual brush",
    }


def _obstacle_competition(
    rgb: np.ndarray,
    candidate: np.ndarray,
    semantic_obstacle: np.ndarray,
    roi: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Remove only pixels supported by obstacle evidence; preserve ambiguous bars."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    vegetation = (
        (hsv[:, :, 0] >= 25)
        & (hsv[:, :, 0] <= 100)
        & (hsv[:, :, 1] >= 42)
        & (hsv[:, :, 2] >= 28)
    )
    vegetation = cv2.morphologyEx(vegetation.astype(np.uint8), cv2.MORPH_OPEN, _kernel(3), iterations=1) > 0
    local_mean = cv2.GaussianBlur(lab, (0, 0), 3.2)
    local_sq = cv2.GaussianBlur(lab ** 2, (0, 0), 3.2)
    texture = np.sqrt(np.maximum(0.0, (local_sq - local_mean ** 2).mean(axis=2)))
    edges = cv2.Canny(gray, 35, 125) > 0
    line_support = cv2.dilate(edges.astype(np.uint8), _kernel(5), iterations=1) > 0
    texture_limit = float(np.percentile(texture[roi], 94)) if np.any(roi) else float(np.percentile(texture, 94))
    rough_non_line = (texture > texture_limit) & ~line_support
    exclusion = semantic_obstacle | vegetation | rough_non_line
    result = candidate & roi & ~exclusion
    result = cv2.morphologyEx(result.astype(np.uint8), cv2.MORPH_CLOSE, _kernel(3), iterations=1) > 0
    return result, {
        "semantic_obstacle_pixels": int(np.count_nonzero(candidate & semantic_obstacle)),
        "vegetation_pixels": int(np.count_nonzero(candidate & vegetation)),
        "rough_non_line_pixels": int(np.count_nonzero(candidate & rough_non_line)),
        "texture_threshold": round(texture_limit, 3),
        "policy": "evidence-only obstacle removal; ambiguous pixels are retained for width/topology evaluation",
    }


def run_c_sam(rgb: np.ndarray, prompt: dict[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Method C: obstacle-aware, topology-feedback lattice segmentation."""
    stages: dict[str, np.ndarray] = {}
    details: dict[str, Any] = {}
    stage_times: dict[str, float] = {}

    started = time.perf_counter()
    c0, obstacle_mask, sam_meta = run_open_vocabulary_sam2(rgb)
    stages["C0"] = c0
    details["C0"] = {"module": "open_vocabulary_localization_plus_raw_sam2", **sam_meta}
    stage_times["C0"] = time.perf_counter() - started

    tick = time.perf_counter()
    automatic_box = sam_meta.get("selected_detection", {}).get("box")
    roi, roi_meta = _estimate_roi_mask(rgb, {"box": automatic_box})
    c1, edge_meta = _edge_guided_refinement(rgb, c0, roi)
    stages["C1"] = c1
    details["C1"] = {"module": "edge_guided_boundary_refinement", **roi_meta, **edge_meta}
    stage_times["C1"] = time.perf_counter() - tick

    tick = time.perf_counter()
    c2, background_meta = _obstacle_competition(rgb, c1, obstacle_mask, roi)
    stages["C2"] = c2
    details["C2"] = {
        "module": "semantic_obstacle_competition_and_background_suppression",
        **background_meta,
        "obstacle_proposals": sam_meta.get("obstacle_proposals", []),
    }
    stage_times["C2"] = time.perf_counter() - tick

    tick = time.perf_counter()
    c3, width_meta = _width_filter(c2, roi)
    stages["C3"] = c3
    details["C3"] = {"module": "bar_width_filter", **width_meta}
    stage_times["C3"] = time.perf_counter() - tick

    tick = time.perf_counter()
    c4, cleanup_meta = _remove_noise_and_spurs(c3)
    stages["C4"] = c4
    details["C4"] = {"module": "topology_feedback_component_and_spur_cleanup", **cleanup_meta}
    stage_times["C4"] = time.perf_counter() - tick

    tick = time.perf_counter()
    c5, gap_meta = _connect_gaps(c4, rgb)
    stages["C5"] = c5
    inferred_mask = c5 & ~c4
    details["C5"] = {
        "module": "evidence_constrained_occlusion_completion",
        **gap_meta,
        "observed_pixels": int(c4.sum()),
        "inferred_pixels": int(inferred_mask.sum()),
    }
    stage_times["C5"] = time.perf_counter() - tick

    tick = time.perf_counter()
    c6, topology_meta = _topology_repair(c5, roi, rgb)
    stages["C6"] = c6
    details["C6"] = {"module": "global_topology_feedback_and_structured_output", **topology_meta}
    stage_times["C6"] = time.perf_counter() - tick

    for name, stage_mask in stages.items():
        details[name]["metrics"] = _structural_metrics(stage_mask, rgb)
        details[name]["stage_duration_seconds"] = round(stage_times[name], 4)
    metadata = {
        "method": "obstacle_aware_topology_feedback_lattice_segmentation",
        "algorithm_version": "lattice_oatf_v2_zero_shot",
        "definition": "Open-vocabulary SAM2 initial mask plus edge refinement, semantic obstacle competition, bar-width constraints, topology feedback, evidence-constrained gap completion and structured output",
        "scientific_name_zh": "障碍感知与拓扑反馈窗棂分割",
        "training_or_finetuning": False,
        "manual_brush": False,
        "manual_box_or_points": False,
        "stage_order": list(stages),
        "stages": details,
        "_artifact_masks": {
            "obstacle": obstacle_mask,
            "observed": c4,
            "inferred": inferred_mask,
        },
        "total_stage_duration_seconds": round(sum(stage_times.values()), 4),
        "ground_truth_metrics_status": "pending_second_review",
    }
    return stages, metadata


ECO_DATASET_ROOT = EXPERIMENT_ROOT / "09_三技术统一测试集_30张"
ECO_GROUND_TRUTH_ROOT = ECO_DATASET_ROOT / "01.5_人工真值_待人工复核"
ECO_LEGACY_C_ROOT = ECO_DATASET_ROOT / "03_障碍感知与拓扑反馈窗棂分割"
ECO_V01_DEVELOPMENT_ROOT = EXPERIMENT_ROOT / "11_ECO-Lattice_开发验证_不覆盖旧结果"
ECO_DEVELOPMENT_ROOT = EXPERIMENT_ROOT / "12_ECO-Lattice_多先验遮挡补全_开发验证_不覆盖旧结果"


def _eco_illumination_normalize(gray: np.ndarray) -> tuple[np.ndarray, float]:
    """A light-weight single-image Retinex-style normalisation.

    It deliberately normalises illumination only. It never creates a missing bar
    and it is independent of the manual reference masks.
    """
    sigma = max(5.0, min(gray.shape[:2]) * 0.024)
    log_gray = np.log1p(gray.astype(np.float32) / 255.0)
    base = cv2.GaussianBlur(log_gray, (0, 0), sigmaX=sigma, sigmaY=sigma)
    normalised = cv2.normalize(log_gray - base, None, 0, 255, cv2.NORM_MINMAX)
    return normalised.astype(np.uint8), float(sigma)


def _eco_texture_strength(gray: np.ndarray) -> np.ndarray:
    gray_float = gray.astype(np.float32)
    mean = cv2.GaussianBlur(gray_float, (0, 0), sigmaX=2.0, sigmaY=2.0)
    square_mean = cv2.GaussianBlur(gray_float ** 2, (0, 0), sigmaX=2.0, sigmaY=2.0)
    return np.sqrt(np.maximum(0.0, square_mean - mean ** 2))


def _eco_vegetation_mask(hsv: np.ndarray) -> np.ndarray:
    """A conservative cue, not a semantic label.

    Greenish pixels are treated as *interference evidence* only. A visible bar is
    not discarded merely because vegetation is seen through its opening.
    """
    raw = (
        (hsv[:, :, 0] >= 25)
        & (hsv[:, :, 0] <= 100)
        & (hsv[:, :, 1] >= 42)
        & (hsv[:, :, 2] >= 28)
    )
    return cv2.morphologyEx(raw.astype(np.uint8), cv2.MORPH_OPEN, _kernel(3), iterations=1) > 0


def _eco_remove_tiny_components(mask: np.ndarray) -> tuple[np.ndarray, int, int]:
    """Remove isolated pixel noise without deleting small ornamental components."""
    minimum_area = max(7, int(round(mask.size * 0.000025)))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    output = np.zeros(mask.shape, dtype=np.uint8)
    removed = 0
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area >= minimum_area:
            output[labels == label] = 1
        else:
            removed += 1
    return output.astype(bool), minimum_area, removed


def _eco_endpoint_direction(skeleton: np.ndarray, point: tuple[int, int], radius: int = 7) -> np.ndarray | None:
    """Estimate the inward tangent around a skeleton endpoint."""
    x, y = point
    yy, xx = np.where(skeleton)
    if xx.size == 0:
        return None
    dx = xx.astype(np.float32) - float(x)
    dy = yy.astype(np.float32) - float(y)
    distance = np.hypot(dx, dy)
    eligible = (distance >= 2.0) & (distance <= float(radius))
    if not np.any(eligible):
        return None
    index = int(np.argmax(np.where(eligible, distance, -1.0)))
    vector = np.array([dx[index], dy[index]], dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > 1e-6 else None


def _eco_conservative_bridges(
    visible_mask: np.ndarray,
    candidate_mask: np.ndarray,
    interference: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Produce a clearly separated candidate bridge layer.

    The returned pixels are never merged into ``M_visible``. This implements the
    evidence/assumption separation required by the paper: a bridge is allowed only
    when endpoint tangent, width and local obstacle evidence agree.
    """
    skeleton = _skeleton(visible_mask) > 0
    neighbors = _neighbor_count(skeleton)
    ys, xs = np.where(skeleton & (neighbors == 1))
    endpoints = [(int(x), int(y)) for y, x in zip(ys, xs)]
    if len(endpoints) > 180:
        return np.zeros_like(visible_mask, dtype=bool), {
            "endpoint_count": len(endpoints),
            "bridge_count": 0,
            "policy": "skipped_dense_endpoint_field_to_avoid_speculative_completion",
        }

    distance = cv2.distanceTransform(visible_mask.astype(np.uint8), cv2.DIST_L2, 5)
    width_values = distance[skeleton] * 2.0
    median_width = float(np.median(width_values)) if width_values.size else 0.0
    maximum_gap = max(5, int(round(min(visible_mask.shape) * 0.022)))
    bridge = np.zeros_like(visible_mask, dtype=np.uint8)
    used: set[int] = set()
    accepted: list[dict[str, Any]] = []
    for index, p0 in enumerate(endpoints):
        if index in used:
            continue
        d0 = _eco_endpoint_direction(skeleton, p0)
        if d0 is None:
            continue
        choices: list[tuple[float, int, tuple[int, int], float, float, float, float, float]] = []
        for other_index in range(index + 1, len(endpoints)):
            if other_index in used:
                continue
            p1 = endpoints[other_index]
            delta = np.array([p1[0] - p0[0], p1[1] - p0[1]], dtype=np.float32)
            gap = float(np.linalg.norm(delta))
            if gap < 3.0 or gap > maximum_gap:
                continue
            direction = delta / max(gap, 1e-6)
            d1 = _eco_endpoint_direction(skeleton, p1)
            if d1 is None:
                continue
            tangent_agreement = min(float(-np.dot(d0, direction)), float(np.dot(d1, direction)))
            if tangent_agreement < 0.72:
                continue
            width0 = float(distance[p0[1], p0[0]] * 2.0)
            width1 = float(distance[p1[1], p1[0]] * 2.0)
            if abs(width0 - width1) > max(2.0, median_width * 0.45):
                continue
            line = np.zeros_like(visible_mask, dtype=np.uint8)
            cv2.line(line, p0, p1, 1, 1, cv2.LINE_8)
            line_pixels = line > 0
            candidate_support = float(np.count_nonzero(candidate_mask & line_pixels) / max(1, int(line_pixels.sum())))
            obstacle_support = float(np.count_nonzero(interference & line_pixels) / max(1, int(line_pixels.sum())))
            # Require either weak visible evidence or an actual obstacle signal. A
            # clean empty region must not be invented as a missing lattice bar.
            if candidate_support < 0.55 or obstacle_support < 0.18:
                continue
            score = tangent_agreement + candidate_support * 0.45 + obstacle_support * 0.20 - gap / max(1.0, maximum_gap) * 0.18
            choices.append((score, other_index, p1, gap, tangent_agreement, obstacle_support, width0, width1))
        if not choices:
            continue
        _, other_index, p1, gap, tangent_agreement, obstacle_support, width0, width1 = max(choices, key=lambda item: item[0])
        cv2.line(bridge, p0, p1, 1, max(1, int(round(max(width0, width1) / 2.0))), cv2.LINE_AA)
        used.update((index, other_index))
        accepted.append({
            "from": list(p0),
            "to": list(p1),
            "gap_pixels": round(gap, 3),
            "tangent_agreement": round(tangent_agreement, 3),
            "obstacle_support": round(obstacle_support, 3),
        })
    return bridge.astype(bool), {
        "endpoint_count": len(endpoints),
        "median_width_pixels": round(median_width, 3),
        "maximum_gap_pixels": maximum_gap,
        "bridge_count": len(accepted),
        "bridges": accepted,
        "policy": "candidate_layer_only_not_merged_into_visible_mask",
    }


def _eco_hough_window_roi(rgb: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    """Prefer a long-line window frame when it is strongly supported.

    The earlier irregular-contour ROI can absorb a wall or foreground rock.  This
    detector only replaces it when two long, well-separated vertical frame edges
    are present; circular and irregular windows continue to use the old fallback.
    """
    fallback, fallback_meta = _estimate_roi_mask(rgb, {})
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    height, width = gray.shape
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 40, 120)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180.0,
        threshold=max(35, min(height, width) // 10),
        minLineLength=int(min(height, width) * 0.26),
        maxLineGap=int(min(height, width) * 0.04),
    )
    if lines is None:
        return fallback, fallback_meta

    vertical: list[tuple[int, int, int, int]] = []
    horizontal: list[tuple[int, int, int, int]] = []
    for x0, y0, x1, y1 in lines.reshape(-1, 4):
        dx = abs(int(x1) - int(x0))
        dy = abs(int(y1) - int(y0))
        if dy > dx * 5:
            vertical.append((int((x0 + x1) / 2), dy, min(int(y0), int(y1)), max(int(y0), int(y1))))
        if dx > dy * 5:
            horizontal.append((int((y0 + y1) / 2), dx, min(int(x0), int(x1)), max(int(x0), int(x1))))

    left = sorted((line for line in vertical if line[0] < width * 0.38), key=lambda item: -item[1])
    right = sorted((line for line in vertical if line[0] > width * 0.62), key=lambda item: -item[1])
    if not left or not right or right[0][0] - left[0][0] <= width * 0.42:
        return fallback, fallback_meta

    top = sorted((line for line in horizontal if line[0] < height * 0.38), key=lambda item: -item[1])
    bottom = sorted((line for line in horizontal if line[0] > height * 0.62), key=lambda item: -item[1])
    left_line, right_line = left[0], right[0]
    pad_x = int(round(width * 0.065))
    pad_y = int(round(height * 0.025))
    x0 = max(0, left_line[0] - pad_x)
    x1 = min(width - 1, right_line[0] + pad_x)
    y0 = max(0, min(left_line[2], right_line[2]) - pad_y)
    y1 = min(height - 1, max(left_line[3], right_line[3]) + pad_y)
    if top:
        y0 = min(y0, max(0, top[0][0] - pad_y))
    if bottom and bottom[0][0] > y0 + height * 0.45:
        y1 = max(y1, min(height - 1, bottom[0][0] + pad_y))

    roi = np.zeros((height, width), dtype=np.uint8)
    roi[y0:y1 + 1, x0:x1 + 1] = 1
    coverage = float(roi.mean())
    # A partial pair of internal mullions can look like a window frame.  Reject
    # rectangles that crop away too much of the image (A01 is the canonical
    # failure: the old ROI started below the top third of the lattice).
    if coverage < 0.62 or coverage > 0.93:
        return fallback, fallback_meta
    return roi.astype(bool), {
        "roi_source": "long_frame_line_pair",
        "roi_coverage": round(coverage, 6),
        "roi_polygon": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
        "perspective_normalization": "source-image coordinates; no forced four-corner warp",
        "frame_line_support": {
            "left_length": left_line[1],
            "right_length": right_line[1],
        },
    }


def _eco_frame_first_roi(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    """Detect the architectural boundary before segmenting its ornament.

    The lattice boundary is a structural object, not just another colour region.
    Four low-complexity families are admitted: rectangle, square, circle and
    ellipse.  The returned masks are (interior ROI, full parametric frame,
    image-supported part of the frame).  This keeps vegetation and masonry
    outside the opening from competing with the inner lattice and gives the 2.5D
    stage an explicit, closed boundary even when a short part is occluded.
    """
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    height, width = gray.shape
    minimum = min(height, width)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 35, 115) > 0
    edge_near = cv2.dilate(edges.astype(np.uint8), _kernel(max(3, int(round(minimum * 0.012)) | 1)), iterations=1) > 0

    def smooth_profile(values: np.ndarray, sigma: float) -> np.ndarray:
        return cv2.GaussianBlur(values.astype(np.float32).reshape(1, -1), (0, 0), sigma).reshape(-1)

    vertical_profile = smooth_profile(np.mean(edge_near, axis=0), max(2.0, width * 0.007))
    horizontal_profile = smooth_profile(np.mean(edge_near, axis=1), max(2.0, height * 0.007))

    def best_side(profile: np.ndarray, start: int, stop: int, outer_side: str) -> tuple[int, float]:
        indices = np.arange(max(0, start), min(len(profile), stop))
        if indices.size == 0:
            return 0, 0.0
        position = indices / max(1.0, float(len(profile) - 1))
        if outer_side in {"left", "top"}:
            prior = 1.0 - np.clip(position / 0.42, 0.0, 1.0)
        else:
            prior = np.clip((position - 0.58) / 0.42, 0.0, 1.0)
        local = profile[indices]
        scale = max(1e-6, float(np.percentile(profile, 96)))
        # The architectural frame is normally the outermost long support. Give
        # position a substantial prior so a stronger internal mullion cannot be
        # mistaken for the frame boundary.
        scores = local / scale * 0.60 + prior * 0.40
        best_index = int(np.argmax(scores))
        return int(indices[best_index]), float(local[best_index] / scale)

    rx0, sx0 = best_side(vertical_profile, int(width * 0.01), int(width * 0.40), "left")
    rx1, sx1 = best_side(vertical_profile, int(width * 0.60), int(width * 0.99), "right")
    ry0, sy0 = best_side(horizontal_profile, int(height * 0.01), int(height * 0.40), "top")
    ry1, sy1 = best_side(horizontal_profile, int(height * 0.60), int(height * 0.99), "bottom")
    rect_width = rx1 - rx0
    rect_height = ry1 - ry0
    rectangle_valid = rect_width >= width * 0.48 and rect_height >= height * 0.48
    rectangle_score = float(np.mean([sx0, sx1, sy0, sy1])) if rectangle_valid else 0.0
    rectangle_score *= float(np.clip((rect_width * rect_height) / max(1.0, width * height) / 0.72, 0.55, 1.0))

    # Long Hough segments are more trustworthy than a local projection peak.
    hough_roi, hough_meta = _eco_hough_window_roi(rgb)
    if hough_meta.get("roi_source") == "long_frame_line_pair":
        polygon = hough_meta.get("roi_polygon", [])
        if len(polygon) == 4:
            hx0, hy0 = polygon[0]
            hx1, hy1 = polygon[2]
            left_margin = float(hx0) / max(1.0, width)
            right_margin = float(width - 1 - hx1) / max(1.0, width)
            top_margin = float(hy0) / max(1.0, height)
            bottom_margin = float(height - 1 - hy1) / max(1.0, height)
            balanced_outer_frame = abs(left_margin - right_margin) <= 0.12 and abs(top_margin - bottom_margin) <= 0.18
            hough_score = 0.76
            if balanced_outer_frame and hough_score > rectangle_score:
                rx0, ry0, rx1, ry1 = int(hx0), int(hy0), int(hx1), int(hy1)
                rect_width, rect_height = rx1 - rx0, ry1 - ry0
                rectangle_score = hough_score
                rectangle_valid = True

    # An irregular outer-contour fallback is useful for asymmetric photographs:
    # one side of the window may be close to the crop while a large wall strip
    # remains on the other side.  Adopt only clearly inboard contour sides; keep
    # projection/Hough estimates for crop-touching sides.
    fallback_roi, _fallback_meta = _estimate_roi_mask(rgb, {})
    fys, fxs = np.where(fallback_roi)
    if fxs.size:
        fx0, fx1 = int(fxs.min()), int(fxs.max())
        fy0, fy1 = int(fys.min()), int(fys.max())
        if fx0 > width * 0.015:
            rx0 = min(rx0, fx0)
        if fx1 < width * 0.95:
            rx1 = fx1
        if fy0 > height * 0.02:
            ry0 = min(ry0, fy0)
        if fy1 < height * 0.90:
            ry1 = fy1
        rect_width = rx1 - rx0
        rect_height = ry1 - ry0
        rectangle_valid = rect_width >= width * 0.48 and rect_height >= height * 0.48

    best_ellipse: dict[str, Any] | None = None
    contours, _ = cv2.findContours(edges.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    for contour in contours:
        if len(contour) < 40:
            continue
        x, y, cw, ch = cv2.boundingRect(contour)
        if cw < width * 0.43 or ch < height * 0.43:
            continue
        if cw > width * 0.98 and ch > height * 0.98:
            continue
        if not (0.45 <= cw / max(1.0, ch) <= 2.2):
            continue
        try:
            (cx, cy), (axis_a, axis_b), angle = cv2.fitEllipse(contour)
        except cv2.error:
            continue
        if axis_a < width * 0.42 or axis_b < height * 0.42:
            continue
        if abs(cx - width / 2.0) > width * 0.24 or abs(cy - height / 2.0) > height * 0.24:
            continue
        perimeter = np.zeros_like(gray, dtype=np.uint8)
        cv2.ellipse(perimeter, ((int(round(cx)), int(round(cy))), (int(round(axis_a)), int(round(axis_b))), float(angle)), 1, max(2, int(round(minimum * 0.018))))
        support = float(np.count_nonzero((perimeter > 0) & edge_near) / max(1, np.count_nonzero(perimeter)))
        area_ratio = float(np.pi * axis_a * axis_b * 0.25 / max(1.0, width * height))
        score = support * 0.76 + min(1.0, area_ratio / 0.48) * 0.16 + (1.0 - min(1.0, abs(cx - width / 2.0) / (width * 0.25) + abs(cy - height / 2.0) / (height * 0.25))) * 0.08
        if best_ellipse is None or score > best_ellipse["score"]:
            best_ellipse = {"center": (float(cx), float(cy)), "axes": (float(axis_a), float(axis_b)), "angle": float(angle), "score": float(score), "support": support, "area_ratio": area_ratio}

    choose_ellipse = bool(best_ellipse and best_ellipse["score"] >= max(0.42, rectangle_score + 0.04))
    roi_u8 = np.zeros_like(gray, dtype=np.uint8)
    frame_u8 = np.zeros_like(gray, dtype=np.uint8)
    thickness = max(3, int(round(minimum * 0.028)))
    if choose_ellipse and best_ellipse is not None:
        cx, cy = best_ellipse["center"]
        axis_a, axis_b = best_ellipse["axes"]
        ellipse = ((int(round(cx)), int(round(cy))), (int(round(axis_a)), int(round(axis_b))), best_ellipse["angle"])
        cv2.ellipse(roi_u8, ellipse, 1, -1)
        cv2.ellipse(frame_u8, ellipse, 1, thickness)
        ratio = max(axis_a, axis_b) / max(1.0, min(axis_a, axis_b))
        frame_shape = "circle" if ratio <= 1.12 else "ellipse"
        geometry: dict[str, Any] = {"center": [round(cx, 2), round(cy, 2)], "axes": [round(axis_a, 2), round(axis_b, 2)], "angle_degrees": round(best_ellipse["angle"], 2)}
        confidence = float(best_ellipse["score"])
        boundary_support = float(best_ellipse["support"])
    else:
        if not rectangle_valid:
            fallback, _ = _estimate_roi_mask(rgb, {})
            ys, xs = np.where(fallback)
            if xs.size:
                rx0, rx1, ry0, ry1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
            else:
                rx0, rx1, ry0, ry1 = int(width * 0.04), int(width * 0.96), int(height * 0.04), int(height * 0.96)
            rectangle_score = 0.25
        pad = max(1, thickness // 3)
        rx0, rx1 = max(0, rx0 - pad), min(width - 1, rx1 + pad)
        ry0, ry1 = max(0, ry0 - pad), min(height - 1, ry1 + pad)
        cv2.rectangle(roi_u8, (rx0, ry0), (rx1, ry1), 1, -1)
        cv2.rectangle(frame_u8, (rx0, ry0), (rx1, ry1), 1, thickness)
        ratio = (rx1 - rx0) / max(1.0, float(ry1 - ry0))
        frame_shape = "square" if 0.88 <= ratio <= 1.12 else "rectangle"
        geometry = {"bbox_xyxy": [rx0, ry0, rx1, ry1], "aspect_ratio": round(ratio, 4)}
        confidence = float(np.clip(rectangle_score, 0.0, 1.0))
        boundary_support = float(np.count_nonzero((frame_u8 > 0) & edge_near) / max(1, np.count_nonzero(frame_u8)))

    roi = roi_u8 > 0
    frame = (frame_u8 > 0) & roi
    # Observed frame needs local image evidence; the closed parametric remainder
    # is stored as an inferred structural layer rather than forged as observation.
    frame_observed = frame & edge_near
    frame_observed = cv2.dilate(frame_observed.astype(np.uint8), _kernel(3), iterations=1) > 0
    frame_observed &= frame
    return roi, frame, frame_observed, {
        "module": "frame_first_parametric_boundary_detector",
        "frame_shape": frame_shape,
        "frame_confidence": round(confidence, 4),
        "boundary_image_support": round(boundary_support, 4),
        "geometry": geometry,
        "frame_thickness_pixels": thickness,
        "roi_coverage": round(float(np.mean(roi)), 6),
        "frame_pixels": int(np.count_nonzero(frame)),
        "frame_observed_pixels": int(np.count_nonzero(frame_observed)),
        "frame_inferred_pixels": int(np.count_nonzero(frame & ~frame_observed)),
        "allowed_families": ["square", "rectangle", "circle", "ellipse"],
        "policy": "detect and lock the architectural frame before internal pattern extraction; pixels outside the frame ROI are forbidden",
    }


def _eco_directional_continuity_candidates(
    visible: np.ndarray,
    weak_evidence: np.ndarray,
    occluder: np.ndarray,
    roi: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Reconnect short fragmented rods with orientation-aware local closings."""
    minimum = min(visible.shape)
    line_length = max(5, int(round(minimum * 0.016)) | 1)
    kernels = [
        np.ones((1, line_length), dtype=np.uint8),
        np.ones((line_length, 1), dtype=np.uint8),
        np.eye(line_length, dtype=np.uint8),
        np.fliplr(np.eye(line_length, dtype=np.uint8)),
    ]
    proposed = np.zeros_like(visible, dtype=bool)
    source = visible.astype(np.uint8)
    for line_kernel in kernels:
        closed = cv2.morphologyEx(source, cv2.MORPH_CLOSE, line_kernel, iterations=1) > 0
        proposed |= closed & ~visible
    support_radius = max(5, int(round(minimum * 0.020)) | 1)
    near_observed = cv2.dilate(source, _kernel(support_radius), iterations=1) > 0
    evidence_gate = weak_evidence | (cv2.dilate(occluder.astype(np.uint8), _kernel(support_radius), iterations=1) > 0)
    candidate = proposed & near_observed & evidence_gate & roi
    minimum_area = max(2, int(round(visible.size * 0.000006)))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(candidate.astype(np.uint8), connectivity=8)
    filtered = np.zeros_like(candidate, dtype=bool)
    removed = 0
    visible_skeleton = _skeleton(visible) > 0
    visible_distance = cv2.distanceTransform(visible.astype(np.uint8), cv2.DIST_L2, 5)
    widths = visible_distance[visible_skeleton] * 2.0
    dominant_width = float(np.median(widths)) if widths.size else 5.0
    maximum_width = max(5.0, dominant_width * 1.6)
    component_records: list[tuple[float, int, np.ndarray]] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        component = labels == label
        if area < minimum_area:
            removed += 1
            continue
        distance = cv2.distanceTransform(component.astype(np.uint8), cv2.DIST_L2, 5)
        component_width = float(np.percentile(distance[component] * 2.0, 90)) if np.any(component) else 0.0
        touch = (cv2.dilate(component.astype(np.uint8), _kernel(5), iterations=1) > 0) & visible
        touch_count, _, touch_stats, _ = cv2.connectedComponentsWithStats(touch.astype(np.uint8), connectivity=8)
        anchors = sum(1 for index in range(1, touch_count) if int(touch_stats[index, cv2.CC_STAT_AREA]) >= 2)
        if component_width > maximum_width or anchors < 2:
            removed += 1
            continue
        component_records.append((anchors * 10.0 + np.log1p(area), area, component))
    budget = max(minimum_area * 4, int(np.count_nonzero(visible) * 0.12))
    selected_area = 0
    for _score, area, component in sorted(component_records, key=lambda item: item[0], reverse=True):
        if selected_area + area > budget:
            removed += 1
            continue
        filtered |= component
        selected_area += area
    candidate = filtered
    before_skeleton = _skeleton(visible) > 0
    after_skeleton = _skeleton(visible | candidate) > 0
    before_endpoints = int(np.count_nonzero(before_skeleton & (_neighbor_count(before_skeleton) == 1)))
    after_endpoints = int(np.count_nonzero(after_skeleton & (_neighbor_count(after_skeleton) == 1)))
    return candidate, {
        "line_length_pixels": line_length,
        "candidate_pixels": int(np.count_nonzero(candidate)),
        "endpoints_before": before_endpoints,
        "endpoints_after": after_endpoints,
        "endpoint_reduction": before_endpoints - after_endpoints,
        "minimum_component_area": minimum_area,
        "dominant_visible_width_pixels": round(dominant_width, 3),
        "maximum_candidate_width_pixels": round(maximum_width, 3),
        "candidate_budget_pixels": budget,
        "removed_tiny_components": removed,
        "policy": "four-orientation short-gap closure constrained by nearby rod evidence or admitted occlusion",
    }


def _eco_nonrod_structural_branch(
    rgb: np.ndarray,
    roi: np.ndarray,
    frame: np.ndarray,
    frame_observed: np.ndarray,
    frame_shape: str | None = None,
) -> tuple[str, np.ndarray | None, np.ndarray | None, np.ndarray | None, dict[str, Any]]:
    """Route sculptural openwork and chromatic relief away from thin-rod logic."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    minimum = min(gray.shape)
    inner = cv2.erode(roi.astype(np.uint8), _kernel(max(9, int(round(minimum * 0.055)) | 1)), iterations=1) > 0
    frame_zone = cv2.dilate(frame.astype(np.uint8), _kernel(5), iterations=1) > 0
    inner_values = gray[inner]
    frame_values = gray[frame_zone]
    frame_saturation_values = hsv[:, :, 1][frame_zone]
    if inner_values.size < 100 or frame_values.size < 30:
        return "uniform_rod_lattice", None, None, None, {"reason": "insufficient_frame_or_inner_samples"}
    otsu_threshold, _ = cv2.threshold(inner_values.reshape(-1, 1), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dark_cut = min(90.0, max(38.0, float(otsu_threshold) * 0.72))
    dark_fraction = float(np.mean(inner_values <= dark_cut))
    frame_luma = float(np.median(frame_values))
    dark_values = inner_values[inner_values <= dark_cut]
    dark_luma = float(np.median(dark_values)) if dark_values.size else float(np.percentile(inner_values, 15))
    frame_saturation = float(np.median(frame_saturation_values)) if frame_saturation_values.size else 0.0

    # Bright stone/wood sculpture against genuinely dark holes: recover the
    # material silhouette, including wide branches, leaves and rock masses.
    if dark_fraction >= 0.24 and frame_luma - dark_luma >= 58.0:
        threshold = float(otsu_threshold)
        foreground = roi & (gray >= threshold)
        foreground = cv2.morphologyEx(foreground.astype(np.uint8), cv2.MORPH_CLOSE, _kernel(5), iterations=1) > 0
        foreground = cv2.morphologyEx(foreground.astype(np.uint8), cv2.MORPH_OPEN, _kernel(3), iterations=1) > 0
        foreground, minimum_area, removed = _eco_remove_tiny_components(foreground)
        foreground |= frame_observed
        remaining_components = max(0, int(cv2.connectedComponents(foreground.astype(np.uint8))[0]) - 1)
        # A genuine wide sculptural panel is a small number of coherent masses.
        # A fragmented light-on-dark result with many narrow components is more
        # likely a rod lattice partly hidden by a solid foreground object.
        if (
            frame_shape in {"square", "rectangle"}
            and remaining_components >= 20
            and dark_fraction < 0.45
        ):
            routed_mode = "occluded_uniform_rod_lattice"
        else:
            routed_mode = "high_contrast_sculptural_openwork"
        edge_gate_pixels = 0
        if routed_mode == "occluded_uniform_rod_lattice":
            # In a rod lattice, a bright background field can pass Otsu just as
            # easily as pale stone.  True rods are bounded by nearby edge pairs;
            # retain only material within a scale-aware edge neighbourhood.
            equalised = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
            rod_edges = cv2.Canny(equalised, 32, 104) > 0
            edge_width = max(7, int(round(minimum * 0.013)) | 1)
            edge_neighbourhood = cv2.dilate(
                rod_edges.astype(np.uint8), _kernel(edge_width), iterations=1
            ) > 0
            foreground &= edge_neighbourhood | frame_observed
            foreground = cv2.morphologyEx(
                foreground.astype(np.uint8), cv2.MORPH_CLOSE, _kernel(5), iterations=1
            ) > 0
            foreground, _, _ = _eco_remove_tiny_components(foreground)
            foreground |= frame_observed
            edge_gate_pixels = int(np.count_nonzero(edge_neighbourhood))
        interference = roi & ~foreground
        uncertain = cv2.dilate(foreground.astype(np.uint8), _kernel(3), iterations=1) > 0
        uncertain &= ~foreground & roi
        return routed_mode, foreground, interference, uncertain, {
            "dark_opening_fraction": round(dark_fraction, 4),
            "otsu_threshold": round(threshold, 3),
            "frame_median_luma": round(frame_luma, 3),
            "dark_opening_median_luma": round(dark_luma, 3),
            "minimum_component_area": minimum_area,
            "removed_tiny_components": removed,
            "remaining_foreground_components": remaining_components,
            "frame_shape_gate": frame_shape,
            "rod_edge_gate_pixels": edge_gate_pixels,
            "policy": (
                "fragmented high-contrast rods with solid-occluder completion enabled"
                if routed_mode == "occluded_uniform_rod_lattice"
                else "wide sculptural material versus true dark openings; equal-width rod filtering disabled"
            ),
        }

    # A coloured relief panel has no through-holes. Learn its material directly
    # from the outer architectural frame; low-chroma rod assumptions are invalid.
    if frame_saturation >= 52.0 and dark_fraction < 0.24:
        samples = lab[frame_zone].reshape(-1, 3)
        if len(samples) > 9000:
            samples = samples[np.linspace(0, len(samples) - 1, 9000).astype(int)]
        cluster_count = min(4, max(2, len(samples) // 1500))
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 60, 0.25)
        cv2.setRNGSeed(6083126)
        _, _, centers = cv2.kmeans(samples.astype(np.float32), cluster_count, None, criteria, 5, cv2.KMEANS_PP_CENTERS)
        # Retain saturated frame-material modes rather than the previous
        # low-chroma modes used for grey stone rods.
        center_chroma = np.linalg.norm(centers[:, 1:3] - 128.0, axis=1)
        centers = centers[np.argsort(center_chroma)[-min(3, len(centers)):]]
        distance = np.min(
            np.stack([np.linalg.norm(lab - center.reshape(1, 1, 3), axis=2) for center in centers]), axis=0
        )
        frame_distances = distance[frame_zone]
        limit = float(np.clip(np.percentile(frame_distances, 90) + 7.0, 20.0, 42.0))
        saturation_floor = max(32.0, frame_saturation * 0.52)
        material = roi & (distance <= limit) & (hsv[:, :, 1] >= saturation_floor)

        # Colour alone cannot distinguish a raised carving from a flat panel
        # made from the same stone/wood. Build a relief response from local
        # shading, ridges and texture, and use colour only as a material gate.
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8)).apply(gray)
        gx = cv2.Sobel(clahe, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(clahe, cv2.CV_32F, 0, 1, ksize=3)
        gradient = cv2.magnitude(gx, gy)
        blur_sigma = max(2.0, minimum * 0.012)
        local_contrast = np.abs(
            clahe.astype(np.float32)
            - cv2.GaussianBlur(clahe.astype(np.float32), (0, 0), blur_sigma)
        )
        texture = _eco_texture_strength(gray).astype(np.float32)
        response_zone = inner if np.count_nonzero(inner) >= 100 else roi
        gradient_limit = float(np.percentile(gradient[response_zone], 72))
        contrast_limit = float(np.percentile(local_contrast[response_zone], 72))
        texture_limit = float(np.percentile(texture[response_zone], 75))
        gradient_extreme = float(np.percentile(gradient[response_zone], 91))
        contrast_extreme = float(np.percentile(local_contrast[response_zone], 91))
        evidence_votes = (
            (gradient >= gradient_limit).astype(np.uint8)
            + (local_contrast >= contrast_limit).astype(np.uint8)
            + (texture >= texture_limit).astype(np.uint8)
        )
        relief_seed = material & (
            (evidence_votes >= 2)
            | (gradient >= gradient_extreme)
            | (local_contrast >= contrast_extreme)
        )
        grow_size = max(5, int(round(minimum * 0.009)) | 1)
        foreground = material & (
            cv2.dilate(relief_seed.astype(np.uint8), _kernel(grow_size), iterations=1) > 0
        )
        foreground = cv2.morphologyEx(
            foreground.astype(np.uint8), cv2.MORPH_CLOSE, _kernel(7), iterations=1
        ) > 0
        foreground = cv2.morphologyEx(
            foreground.astype(np.uint8), cv2.MORPH_OPEN, _kernel(3), iterations=1
        ) > 0

        # Fill compact relief faces (fruit, petals and carved figures), but do
        # not flood-fill the whole rectangular support panel.
        filled = foreground.astype(np.uint8) * 255
        contours, _ = cv2.findContours(filled, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        maximum_fill_area = float(np.count_nonzero(roi)) * 0.035
        compact_fills = 0
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if 35.0 <= area <= maximum_fill_area:
                component = np.zeros_like(filled)
                cv2.drawContours(component, [contour], -1, 255, thickness=-1)
                component_mask = component > 0
                material_ratio = float(np.mean(material[component_mask])) if np.any(component_mask) else 0.0
                if material_ratio >= 0.58:
                    foreground |= component_mask & material
                    compact_fills += 1
        foreground, minimum_area, removed = _eco_remove_tiny_components(foreground)
        foreground |= frame_observed
        interference = roi & ~foreground
        uncertain = (cv2.dilate(foreground.astype(np.uint8), _kernel(5), iterations=1) > 0) & ~foreground & roi
        return "chromatic_solid_relief", foreground, interference, uncertain, {
            "dark_opening_fraction": round(dark_fraction, 4),
            "frame_median_saturation": round(frame_saturation, 3),
            "material_centers_lab": [[round(float(value), 2) for value in center] for center in centers],
            "material_distance_limit": round(limit, 3),
            "saturation_floor": round(saturation_floor, 3),
            "gradient_limit": round(gradient_limit, 3),
            "gradient_extreme_limit": round(gradient_extreme, 3),
            "local_contrast_limit": round(contrast_limit, 3),
            "local_contrast_extreme_limit": round(contrast_extreme, 3),
            "texture_limit": round(texture_limit, 3),
            "relief_seed_pixels": int(np.count_nonzero(relief_seed)),
            "compact_relief_regions_filled": compact_fills,
            "minimum_component_area": minimum_area,
            "removed_tiny_components": removed,
            "policy": "chromatic material gate plus local ridge/shading relief extraction; flat same-colour support is rejected and equal-width rod assumptions are disabled",
        }

    return "uniform_rod_lattice", None, None, None, {
        "dark_opening_fraction": round(dark_fraction, 4),
        "frame_median_saturation": round(frame_saturation, 3),
        "frame_median_luma": round(frame_luma, 3),
        "policy": "retain frame-first thin/variable rod pipeline",
    }


def _eco_boundary_solid_occluder(
    rgb: np.ndarray,
    interference: np.ndarray,
    roi: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Detect a large neutral/rough foreground mass entering from the frame edge."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    texture = _eco_texture_strength(gray).astype(np.float32)
    minimum = min(gray.shape)
    # ``erode`` consumes roughly half the kernel size on each side.  A 42%
    # kernel therefore inspects about the outer 21% of the locked domain,
    # sufficient for foreground rocks that rise well above the sill.
    band_size = max(21, int(round(minimum * 0.42)) | 1)
    boundary_band = roi & ~(
        cv2.erode(roi.astype(np.uint8), _kernel(band_size), iterations=1) > 0
    )
    roi_values = gray[roi]
    dark_limit = float(np.percentile(roi_values, 31)) if roi_values.size else 70.0
    texture_limit = float(np.percentile(texture[roi], 25)) if np.any(roi) else 5.0
    saturation_limit = 92.0
    neutral_dark = (
        interference
        & boundary_band
        & (gray <= min(125.0, dark_limit + 18.0))
        & (hsv[:, :, 1] <= saturation_limit)
    )
    seed = neutral_dark & (texture >= texture_limit)
    candidate = cv2.morphologyEx(
        neutral_dark.astype(np.uint8), cv2.MORPH_CLOSE, _kernel(max(9, int(round(minimum * 0.025)) | 1)), iterations=2
    ) > 0
    labels_count, labels, stats, _ = cv2.connectedComponentsWithStats(candidate.astype(np.uint8), 8)
    selected = np.zeros_like(candidate)
    minimum_area = max(180, int(round(np.count_nonzero(roi) * 0.004)))
    qualified: list[tuple[int, int, int]] = []
    for label in range(1, labels_count):
        component = labels == label
        area = int(stats[label, cv2.CC_STAT_AREA])
        bbox_area = int(stats[label, cv2.CC_STAT_WIDTH]) * int(stats[label, cv2.CC_STAT_HEIGHT])
        fill_ratio = area / max(1, bbox_area)
        seed_support = int(np.count_nonzero(component & seed))
        if (
            area >= minimum_area
            and fill_ratio >= 0.42
            and seed_support >= max(35, int(round(area * 0.06)))
        ):
            qualified.append((area * max(1, seed_support), label, area))
    largest_area = max((area for _, _, area in qualified), default=0)
    retained = [item for item in qualified if item[2] >= max(minimum_area, int(round(largest_area * 0.35)))]
    for _, label, _ in retained:
        selected |= labels == label
    selected_components = len(retained)
    selected = cv2.dilate(selected.astype(np.uint8), _kernel(7), iterations=1) > 0
    selected &= roi
    return selected, {
        "enabled": True,
        "dark_luma_limit": round(min(125.0, dark_limit + 18.0), 3),
        "texture_limit": round(texture_limit, 3),
        "boundary_band_pixels": int(np.count_nonzero(boundary_band)),
        "selected_components": selected_components,
        "selected_pixels": int(np.count_nonzero(selected)),
        "policy": "large neutral textured mass entering from the locked frame boundary; treated as occluder, never as observed lattice",
    }


def _eco_illumination_invariant_rod_extension(
    rgb: np.ndarray,
    visible: np.ndarray,
    roi: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Extend rods across black/grey/white material changes using local contrast."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    clahe = cv2.createCLAHE(clipLimit=2.1, tileGridSize=(8, 8)).apply(gray)
    minimum = min(gray.shape)
    sigma = max(3.0, minimum * 0.022)
    local_delta = np.abs(
        clahe.astype(np.float32)
        - cv2.GaussianBlur(clahe.astype(np.float32), (0, 0), sigma)
    )
    gx = cv2.Sobel(clahe, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(clahe, cv2.CV_32F, 0, 1, ksize=3)
    gradient = cv2.magnitude(gx, gy)
    edges = cv2.Canny(clahe, 28, 92) > 0
    edge_near = cv2.dilate(edges.astype(np.uint8), _kernel(5), iterations=1) > 0
    vegetation = _eco_vegetation_mask(hsv)
    height, width = gray.shape
    counts = {
        "left": int(np.count_nonzero(visible[:, : width // 2])),
        "right": int(np.count_nonzero(visible[:, width // 2 :])),
        "top": int(np.count_nonzero(visible[: height // 2, :])),
        "bottom": int(np.count_nonzero(visible[height // 2 :, :])),
    }
    horizontal_imbalance = abs(counts["left"] - counts["right"]) / max(1, counts["left"] + counts["right"])
    vertical_imbalance = abs(counts["top"] - counts["bottom"]) / max(1, counts["top"] + counts["bottom"])
    target = np.ones_like(roi, dtype=bool)
    target_region = "all"
    overlap_y = max(6, int(round(height * 0.08)))
    overlap_x = max(6, int(round(width * 0.08)))
    if vertical_imbalance >= horizontal_imbalance and vertical_imbalance >= 0.20:
        target[:] = False
        if counts["bottom"] < counts["top"]:
            target[max(0, height // 2 - overlap_y) :, :] = True
            target_region = "bottom"
        else:
            target[: min(height, height // 2 + overlap_y), :] = True
            target_region = "top"
    elif horizontal_imbalance >= 0.20:
        target[:] = False
        if counts["right"] < counts["left"]:
            target[:, max(0, width // 2 - overlap_x) :] = True
            target_region = "right"
        else:
            target[:, : min(width, width // 2 + overlap_x)] = True
            target_region = "left"
    sample_zone = roi & ~vegetation
    contrast_limit = float(np.percentile(local_delta[sample_zone], 72)) if np.any(sample_zone) else 18.0
    gradient_limit = float(np.percentile(gradient[sample_zone], 66)) if np.any(sample_zone) else 70.0
    visible_saturation = hsv[:, :, 1][visible & ~vegetation]
    saturation_limit = float(np.clip(
        (np.percentile(visible_saturation, 90) + 18.0) if visible_saturation.size else 76.0,
        58.0,
        100.0,
    ))
    candidate = (
        roi
        & ~vegetation
        & target
        & (hsv[:, :, 1] <= saturation_limit)
        & edge_near
        & (local_delta >= contrast_limit)
        & (gradient >= gradient_limit)
    )
    candidate = cv2.dilate(candidate.astype(np.uint8), _kernel(7), iterations=1) > 0
    candidate &= roi & target & ~vegetation & (hsv[:, :, 1] <= saturation_limit)
    candidate = cv2.morphologyEx(candidate.astype(np.uint8), cv2.MORPH_CLOSE, _kernel(7), iterations=1) > 0
    candidate, minimum_area, removed = _eco_remove_tiny_components(candidate)
    support_radius = max(11, int(round(minimum * 0.05)) | 1)
    support = cv2.dilate(visible.astype(np.uint8), _kernel(support_radius), iterations=1) > 0
    labels_count, labels, stats, _ = cv2.connectedComponentsWithStats(candidate.astype(np.uint8), 8)
    extension = np.zeros_like(candidate)
    kept_components = 0
    for label in range(1, labels_count):
        component = labels == label
        area = int(stats[label, cv2.CC_STAT_AREA])
        support_pixels = int(np.count_nonzero(component & support))
        if area >= minimum_area and support_pixels >= max(2, int(round(area * 0.025))):
            extension |= component
            kept_components += 1
    extension &= ~visible & roi
    return extension, {
        "enabled": True,
        "contrast_limit": round(contrast_limit, 3),
        "gradient_limit": round(gradient_limit, 3),
        "saturation_limit": round(saturation_limit, 3),
        "support_radius_pixels": support_radius,
        "target_region": target_region,
        "left_right_imbalance": round(horizontal_imbalance, 4),
        "top_bottom_imbalance": round(vertical_imbalance, 4),
        "candidate_pixels": int(np.count_nonzero(candidate)),
        "extension_pixels": int(np.count_nonzero(extension)),
        "kept_components": kept_components,
        "removed_tiny_components": removed,
        "policy": "local bright/dark contrast is invariant to global illumination and material polarity; only edge-supported components near the observed graph are added",
    }


def _eco_multiscale_visible_evidence(
    rgb: np.ndarray,
    roi: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    """Create a zero-training visible-material trimap and solve it with GrabCut.

    The trimap is image-internal: frame material clusters, multi-scale bright/dark
    ribbon responses, paired-edge neighbourhoods and vegetation/texture evidence.
    GrabCut is used only as a deterministic graph optimiser over those seeds.
    """
    height, width = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    edges = cv2.Canny(clahe, 35, 105) > 0
    edge_near = cv2.dilate(edges.astype(np.uint8), _kernel(5), iterations=1) > 0

    bright_ribbon = np.zeros_like(gray)
    dark_ribbon = np.zeros_like(gray)
    scales: list[int] = []
    for fraction in (0.018, 0.032, 0.055):
        size = max(9, int(round(min(height, width) * fraction)) | 1)
        scales.append(size)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
        bright_ribbon = np.maximum(bright_ribbon, cv2.morphologyEx(clahe, cv2.MORPH_TOPHAT, kernel))
        dark_ribbon = np.maximum(dark_ribbon, cv2.morphologyEx(clahe, cv2.MORPH_BLACKHAT, kernel))

    band = max(6, int(round(min(height, width) * 0.04)))
    inner = cv2.erode(roi.astype(np.uint8), _kernel(band * 2 + 1), iterations=1) > 0
    frame_band = roi & ~inner
    vegetation = _eco_vegetation_mask(hsv)
    texture = _eco_texture_strength(gray)
    texture_limit = float(np.percentile(texture[roi], 88)) if np.any(roi) else float(np.percentile(texture, 88))
    rough = texture >= texture_limit

    samples = lab[frame_band & edge_near & ~vegetation].reshape(-1, 3).astype(np.float32)
    if len(samples) < 50:
        samples = lab[frame_band & ~vegetation].reshape(-1, 3).astype(np.float32)
    if len(samples) > 12000:
        samples = samples[np.linspace(0, len(samples) - 1, 12000).astype(int)]
    if len(samples) >= 40:
        cluster_count = min(5, max(2, len(samples) // 800))
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 60, 0.3)
        cv2.setRNGSeed(31082026)
        _, _, centers = cv2.kmeans(samples, cluster_count, None, criteria, 5, cv2.KMEANS_PP_CENTERS)
    else:
        cluster_count = 1
        centers = np.asarray([np.median(lab[roi], axis=0)], dtype=np.float32)
    # Rectangular metal/wood lattices may be darker than the wall behind them,
    # while lime/stone leak windows are usually brighter.  The previous global
    # "bright material" rule therefore filled U01's entire pale background.
    # For a reliable, non-full-frame rectangle, select the prototype closest to
    # the actual perimeter material.  Irregular/full-frame ROIs retain the
    # low-chroma bright-material rule that works for the white stone examples.
    ys_roi, xs_roi = np.where(roi)
    roi_fill = 0.0
    if xs_roi.size:
        bbox_area = max(1, (int(xs_roi.max()) - int(xs_roi.min()) + 1) * (int(ys_roi.max()) - int(ys_roi.min()) + 1))
        roi_fill = float(np.count_nonzero(roi) / bbox_area)
    rectangular_frame = bool(0.60 <= float(np.mean(roi)) <= 0.90 and roi_fill >= 0.96)
    if rectangular_frame:
        keep_count = max(1, min(2, int(np.ceil(len(centers) / 3.0))))
        # The long-frame detector is used for the dark metal/wood window class.
        # Selecting bright low-chroma prototypes in this class labels the pale
        # wall or glass opening instead of the bars (U01).  Preserve two dark
        # modes so both the outer frame and thinner internal bars remain valid.
        centers = centers[np.argsort(centers[:, 0])[:keep_count]]
        prototype_policy = "dark_frame_material_for_rectangular_frame"
    else:
        chroma = np.linalg.norm(centers[:, 1:3] - 128.0, axis=1)
        center_scores = centers[:, 0] - chroma * 0.35
        keep_count = max(1, min(2, int(np.ceil(len(centers) / 2.0))))
        centers = centers[np.argsort(center_scores)[-keep_count:]]
        prototype_policy = "low_chroma_bright_material_for_irregular_frame"
    cluster_count = int(len(centers))
    material_distance = np.min(
        np.stack([np.linalg.norm(lab - center.reshape(1, 1, 3), axis=2) for center in centers]),
        axis=0,
    )
    material_limit = float(np.clip(np.percentile(material_distance[frame_band], 78) + 5.0, 14.0, 28.0)) if np.any(frame_band) else 24.0
    material = material_distance <= material_limit
    saturation = hsv[:, :, 1].astype(np.float32)
    neutral_limit = float(np.percentile(saturation[roi], 58)) if np.any(roi) else float(np.percentile(saturation, 58))
    neutral = saturation <= neutral_limit
    bright_limit = max(10.0, float(np.percentile(bright_ribbon[roi], 75))) if np.any(roi) else 10.0
    dark_limit = max(10.0, float(np.percentile(dark_ribbon[roi], 75))) if np.any(roi) else 10.0
    ribbon = (bright_ribbon >= bright_limit) | (dark_ribbon >= dark_limit)

    definite_foreground = roi & material & neutral & edge_near & ribbon & ~vegetation
    weak_ribbon = (bright_ribbon >= bright_limit * 0.55) | (dark_ribbon >= dark_limit * 0.55)
    strong_ribbon = (bright_ribbon >= bright_limit) | (dark_ribbon >= dark_limit)
    probable_foreground = roi & edge_near & weak_ribbon & material
    probable_foreground |= roi & edge_near & strong_ribbon & neutral & (material_distance <= material_limit * 1.35)
    probable_foreground &= ~(vegetation & ~definite_foreground)
    interference = vegetation | (rough & ~material)

    grabcut = np.full((height, width), cv2.GC_BGD, dtype=np.uint8)
    grabcut[roi] = cv2.GC_PR_BGD
    grabcut[probable_foreground] = cv2.GC_PR_FGD
    grabcut[definite_foreground] = cv2.GC_FGD
    grabcut[(roi & vegetation & ~definite_foreground) | ~roi] = cv2.GC_BGD
    if np.count_nonzero(definite_foreground) >= 30:
        background_model = np.zeros((1, 65), dtype=np.float64)
        foreground_model = np.zeros((1, 65), dtype=np.float64)
        try:
            cv2.grabCut(
                cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
                grabcut,
                None,
                background_model,
                foreground_model,
                4,
                cv2.GC_INIT_WITH_MASK,
            )
            graphcut_visible = ((grabcut == cv2.GC_FGD) | (grabcut == cv2.GC_PR_FGD)) & roi
            # GrabCut is allowed to refine a rod candidate but not to turn a
            # broad, colour-similar wall/glass patch into lattice material.  In
            # the previous build the seven-pixel expansion around probable seeds
            # flooded A01/U01 and made every downstream completion prior invalid.
            # Retain only graph-cut pixels that still possess image evidence.
            evidence_support = probable_foreground | definite_foreground
            evidence_support |= material & edge_near & ribbon & ~vegetation
            conservative_expansion = rectangular_frame or float(np.mean(roi)) > 0.90
            visible = graphcut_visible & evidence_support if conservative_expansion else graphcut_visible
        except cv2.error:
            visible = probable_foreground.copy()
    else:
        visible = probable_foreground.copy()
    support_radius = 3 if (rectangular_frame or float(np.mean(roi)) > 0.90) else 7
    visible &= cv2.dilate(probable_foreground.astype(np.uint8), _kernel(support_radius), iterations=1) > 0
    visible = cv2.morphologyEx(visible.astype(np.uint8), cv2.MORPH_CLOSE, _kernel(5), iterations=1) > 0
    visible = cv2.morphologyEx(visible.astype(np.uint8), cv2.MORPH_OPEN, _kernel(3), iterations=1) > 0
    visible, minimum_area, removed = _eco_remove_tiny_components(visible)
    visible &= roi
    # A built window lattice is one connected load-bearing/ornamental assembly.
    # Disconnected colour-similar fragments are retained as uncertain evidence,
    # not promoted to observed material.  This removes isolated wall, leaf and
    # flower patches without inventing any hidden geometry.
    visible_before_connectivity = visible.copy()
    component_count, component_labels, component_stats, _ = cv2.connectedComponentsWithStats(
        visible.astype(np.uint8), connectivity=8
    )
    selected_component_area = 0
    if component_count > 1:
        largest_label = 1 + int(np.argmax(component_stats[1:, cv2.CC_STAT_AREA]))
        selected_component_area = int(component_stats[largest_label, cv2.CC_STAT_AREA])
        visible = component_labels == largest_label
    connectivity_rejected = visible_before_connectivity & ~visible

    skeleton = _skeleton(visible) > 0
    endpoints = skeleton & (_neighbor_count(skeleton) == 1)
    endpoint_zone = cv2.dilate(endpoints.astype(np.uint8), _kernel(max(9, int(round(min(height, width) * 0.035)) | 1)), iterations=1) > 0
    # Keep endpoint-local occlusion, but also retain coherent dense foreground
    # regions near the observed structure.  The v0.2 endpoint-only gate reduced a
    # large leaf-covered area to scattered specks, leaving SRA/TGC nothing to
    # reconstruct (A01).  Density suppresses ordinary vegetation seen through a
    # clean opening while preserving a contiguous foreground obstacle field.
    density_sigma = max(5.0, float(min(height, width)) * 0.028)
    interference_density = cv2.GaussianBlur(interference.astype(np.float32), (0, 0), density_sigma)
    density_values = interference_density[roi]
    density_threshold = max(0.10, float(np.percentile(density_values, 74)) if density_values.size else 0.10)
    dense_interference = interference_density >= density_threshold
    near_structure_radius = max(15, int(round(min(height, width) * 0.085)) | 1)
    near_structure = cv2.dilate(visible.astype(np.uint8), _kernel(near_structure_radius), iterations=1) > 0
    occluder = ((interference & endpoint_zone) | (dense_interference & near_structure)) & roi
    occluder = cv2.morphologyEx(occluder.astype(np.uint8), cv2.MORPH_CLOSE, _kernel(11), iterations=1) > 0
    uncertain = ((probable_foreground & ~visible) | connectivity_rejected | occluder) & roi
    return visible, interference & roi, occluder, uncertain, {
        "material_cluster_count": cluster_count,
        "material_cluster_centers_lab": [[round(float(value), 2) for value in center] for center in centers],
        "material_prototype_policy": prototype_policy,
        "roi_rectangular_frame": rectangular_frame,
        "material_distance_limit": round(material_limit, 3),
        "neutral_saturation_limit": round(neutral_limit, 3),
        "bright_ribbon_limit": round(bright_limit, 3),
        "dark_ribbon_limit": round(dark_limit, 3),
        "ribbon_scales_pixels": scales,
        "definite_foreground_pixels": int(np.count_nonzero(definite_foreground)),
        "probable_foreground_pixels": int(np.count_nonzero(probable_foreground)),
        "minimum_component_area": minimum_area,
        "removed_tiny_components": removed,
        "visible_components_before_connectivity_gate": max(0, int(component_count - 1)),
        "selected_main_component_area": selected_component_area,
        "connectivity_rejected_pixels": int(np.count_nonzero(connectivity_rejected)),
        "graphcut_evidence_support_radius_pixels": support_radius,
        "occluder_pixels": int(np.count_nonzero(occluder)),
        "interference_density_threshold": round(density_threshold, 4),
        "policy": "endpoint-local or dense foreground interference near observed structure",
    }


def _eco_topology_graph_candidates(
    visible: np.ndarray,
    weak_evidence: np.ndarray,
    occluder: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    """TGC: propose medium-range graph edges under endpoint/topology constraints."""
    skeleton = _skeleton(visible) > 0
    neighbors = _neighbor_count(skeleton)
    ys, xs = np.where(skeleton & (neighbors == 1))
    endpoints = [(int(x), int(y)) for y, x in zip(ys, xs)]
    output = np.zeros_like(visible, dtype=np.uint8)
    if len(endpoints) < 2 or len(endpoints) > 180:
        return output.astype(bool), {"endpoint_count": len(endpoints), "candidate_count": 0, "reason": "endpoint_density_gate"}
    distance = cv2.distanceTransform(visible.astype(np.uint8), cv2.DIST_L2, 5)
    minimum_gap = max(5.0, min(visible.shape) * 0.018)
    maximum_gap = max(12.0, min(visible.shape) * 0.085)
    proposals: list[tuple[float, int, int, tuple[int, int], tuple[int, int], float, float, float]] = []
    for i, p0 in enumerate(endpoints):
        tangent0 = _eco_endpoint_direction(skeleton, p0, radius=10)
        if tangent0 is None:
            continue
        for j in range(i + 1, len(endpoints)):
            p1 = endpoints[j]
            delta = np.asarray([p1[0] - p0[0], p1[1] - p0[1]], dtype=np.float32)
            gap = float(np.linalg.norm(delta))
            if gap < minimum_gap or gap > maximum_gap:
                continue
            direction = delta / max(gap, 1e-6)
            tangent1 = _eco_endpoint_direction(skeleton, p1, radius=10)
            if tangent1 is None:
                continue
            tangent_score = min(float(-np.dot(tangent0, direction)), float(np.dot(tangent1, direction)))
            if tangent_score < 0.60:
                continue
            width0 = float(distance[p0[1], p0[0]] * 2.0)
            width1 = float(distance[p1[1], p1[0]] * 2.0)
            width_score = 1.0 - min(1.0, abs(width0 - width1) / max(2.0, max(width0, width1)))
            line = np.zeros_like(output)
            cv2.line(line, p0, p1, 1, 1, cv2.LINE_8)
            path = line > 0
            weak_score = float(np.count_nonzero(path & weak_evidence) / max(1, int(path.sum())))
            occlusion_score = float(np.count_nonzero(path & cv2.dilate(occluder.astype(np.uint8), _kernel(7), iterations=1).astype(bool)) / max(1, int(path.sum())))
            if occlusion_score < 0.12 or weak_score < 0.20:
                continue
            score = tangent_score * 0.42 + width_score * 0.20 + weak_score * 0.18 + occlusion_score * 0.20 - gap / maximum_gap * 0.12
            proposals.append((score, i, j, p0, p1, gap, tangent_score, occlusion_score))
    used: set[int] = set()
    accepted: list[dict[str, Any]] = []
    for score, i, j, p0, p1, gap, tangent_score, occlusion_score in sorted(proposals, reverse=True):
        if i in used or j in used or score < 0.43:
            continue
        local_width = max(1, int(round(max(distance[p0[1], p0[0]], distance[p1[1], p1[0]]))))
        cv2.line(output, p0, p1, 1, local_width, cv2.LINE_AA)
        used.update((i, j))
        accepted.append({
            "from": list(p0),
            "to": list(p1),
            "score": round(score, 4),
            "gap_pixels": round(gap, 3),
            "tangent_score": round(tangent_score, 3),
            "occlusion_support": round(occlusion_score, 3),
        })
        if len(accepted) >= 12:
            break
    return (output > 0) & ~visible, {
        "endpoint_count": len(endpoints),
        "proposal_count": len(proposals),
        "candidate_count": len(accepted),
        "minimum_gap_pixels": round(minimum_gap, 3),
        "maximum_gap_pixels": round(maximum_gap, 3),
        "candidates": accepted,
        "policy": "medium-gap endpoint graph candidates; candidate layer only",
    }


def _eco_sra_candidates(
    visible: np.ndarray,
    occluder: np.ndarray,
    uncertain: np.ndarray,
    roi: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    """SRA: rank mirror/rotation transfers inside actual occlusion fields.

    Unlike v0.2's single global Dice threshold, this route evaluates each
    transform on trusted (unoccluded) support and then checks whether its
    transferred components attach to the observed graph and reduce open ends.
    The result remains an inferred layer; it never overwrites ``visible``.
    """
    ys, xs = np.where(roi)
    if xs.size == 0:
        return np.zeros_like(visible), {"enabled": False, "reason": "empty_roi"}
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    stable, _ = _width_filter(visible, roi)
    stable, _, _ = _eco_remove_tiny_components(stable)
    stable_skeleton = _skeleton(stable) > 0
    stable_distance = cv2.distanceTransform(stable.astype(np.uint8), cv2.DIST_L2, 5)
    stable_widths = stable_distance[stable_skeleton] * 2.0
    stable_width = float(np.median(stable_widths)) if stable_widths.size else 5.0
    pruned_skeleton, _ = _prune_short_spurs(stable_skeleton.astype(np.uint8), max(6, int(round(stable_width * 1.8))))
    reconstruction_radius = max(1, int(round(stable_width * 0.42)))
    stable = cv2.dilate(pruned_skeleton.astype(np.uint8), _kernel(reconstruction_radius * 2 + 1), iterations=1) > 0
    stable &= roi
    crop = stable[y0:y1 + 1, x0:x1 + 1]
    crop_height, crop_width = crop.shape
    left_pixels = int(np.count_nonzero(crop[:, : crop_width // 2]))
    right_pixels = int(np.count_nonzero(crop[:, crop_width // 2 :]))
    top_pixels = int(np.count_nonzero(crop[: crop_height // 2, :]))
    bottom_pixels = int(np.count_nonzero(crop[crop_height // 2 :, :]))
    vertical_imbalance = abs(left_pixels - right_pixels) / max(1, left_pixels + right_pixels)
    horizontal_imbalance = abs(top_pixels - bottom_pixels) / max(1, top_pixels + bottom_pixels)
    occluder_crop = occluder[y0:y1 + 1, x0:x1 + 1]
    left_occlusion = int(np.count_nonzero(occluder_crop[:, : crop_width // 2]))
    right_occlusion = int(np.count_nonzero(occluder_crop[:, crop_width // 2 :]))
    top_occlusion = int(np.count_nonzero(occluder_crop[: crop_height // 2, :]))
    bottom_occlusion = int(np.count_nonzero(occluder_crop[crop_height // 2 :, :]))
    vertical_occlusion_imbalance = abs(left_occlusion - right_occlusion) / max(1, left_occlusion + right_occlusion)
    horizontal_occlusion_imbalance = abs(top_occlusion - bottom_occlusion) / max(1, top_occlusion + bottom_occlusion)
    transforms = {
        "vertical_mirror": np.fliplr(crop),
        "horizontal_mirror": np.flipud(crop),
        "rotation_180": np.flipud(np.fliplr(crop)),
    }
    target_halves: dict[str, np.ndarray] = {
        "vertical_mirror": np.zeros_like(crop, dtype=bool),
        "horizontal_mirror": np.zeros_like(crop, dtype=bool),
        "rotation_180": np.zeros_like(crop, dtype=bool),
    }
    left_deficiency = (right_pixels - left_pixels) / max(1, left_pixels + right_pixels) + (left_occlusion - right_occlusion) / max(1, left_occlusion + right_occlusion)
    if left_deficiency >= 0:
        target_halves["vertical_mirror"][:, : crop_width // 2] = True
    else:
        target_halves["vertical_mirror"][:, crop_width // 2 :] = True
    top_deficiency = (bottom_pixels - top_pixels) / max(1, top_pixels + bottom_pixels) + (top_occlusion - bottom_occlusion) / max(1, top_occlusion + bottom_occlusion)
    if top_deficiency >= 0:
        target_halves["horizontal_mirror"][: crop_height // 2, :] = True
    else:
        target_halves["horizontal_mirror"][crop_height // 2 :, :] = True
    # Rotation is routed quadrant-by-quadrant. Only the weaker member of each
    # diagonal pair receives transferred structure.
    half_h, half_w = crop_height // 2, crop_width // 2
    quadrants = [
        (slice(0, half_h), slice(0, half_w)),
        (slice(0, half_h), slice(half_w, crop_width)),
        (slice(half_h, crop_height), slice(0, half_w)),
        (slice(half_h, crop_height), slice(half_w, crop_width)),
    ]
    quadrant_pixels = [int(np.count_nonzero(crop[yslice, xslice])) for yslice, xslice in quadrants]
    quadrant_occlusion = [int(np.count_nonzero(occluder_crop[yslice, xslice])) for yslice, xslice in quadrants]
    for first, second in ((0, 3), (1, 2)):
        first_deficiency = (quadrant_pixels[second] - quadrant_pixels[first]) / max(1, quadrant_pixels[first] + quadrant_pixels[second]) + (quadrant_occlusion[first] - quadrant_occlusion[second]) / max(1, quadrant_occlusion[first] + quadrant_occlusion[second])
        target = first if first_deficiency >= 0 else second
        yslice, xslice = quadrants[target]
        target_halves["rotation_180"][yslice, xslice] = True
    route_imbalances = {
        "vertical_mirror": max(vertical_imbalance, vertical_occlusion_imbalance),
        "horizontal_mirror": max(horizontal_imbalance, horizontal_occlusion_imbalance),
        "rotation_180": max(
            abs(quadrant_pixels[0] - quadrant_pixels[3]) / max(1, quadrant_pixels[0] + quadrant_pixels[3]),
            abs(quadrant_pixels[1] - quadrant_pixels[2]) / max(1, quadrant_pixels[1] + quadrant_pixels[2]),
        ),
    }
    minimum_area = max(8, int(round(visible.size * 0.000025)))
    gap_radius = max(11, int(round(min(visible.shape) * 0.045)) | 1)
    target_gate = occluder.copy()
    target_gate |= uncertain & (cv2.dilate(occluder.astype(np.uint8), _kernel(gap_radius), iterations=1) > 0)
    target_gate &= roi
    trusted = roi & ~(cv2.dilate(target_gate.astype(np.uint8), _kernel(9), iterations=1) > 0)
    base_skeleton = _skeleton(stable) > 0
    base_endpoint_mask = base_skeleton & (_neighbor_count(base_skeleton) == 1)
    base_endpoints = int(np.count_nonzero(base_endpoint_mask))
    visible_distance = cv2.distanceTransform(stable.astype(np.uint8), cv2.DIST_L2, 5)
    visible_radii = visible_distance[base_skeleton]
    dominant_visible_width = float(np.median(visible_radii) * 2.0) if visible_radii.size else 6.0
    maximum_component_width = max(10.0, dominant_visible_width * 1.8)
    route_results: dict[str, dict[str, Any]] = {}
    for name, transformed in transforms.items():
        transformed_full = np.zeros_like(visible)
        transformed_full[y0:y1 + 1, x0:x1 + 1] = transformed & target_halves[name]
        transformed_for_support = np.zeros_like(visible)
        transformed_for_support[y0:y1 + 1, x0:x1 + 1] = transformed
        overlap = int(np.count_nonzero(visible & transformed_for_support & trusted))
        denom = int(np.count_nonzero(visible & trusted)) + int(np.count_nonzero(transformed_for_support & trusted))
        symmetry = 2.0 * overlap / max(1, denom)
        raw = transformed_full & ~visible & target_gate & roi
        count, labels, stats, _ = cv2.connectedComponentsWithStats(raw.astype(np.uint8), connectivity=8)
        candidate = np.zeros_like(raw)
        anchor_regions_total = 0
        endpoint_anchors_total = 0
        removed = 0
        component_records: list[tuple[float, int, int, int, np.ndarray]] = []
        for label in range(1, count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < minimum_area:
                removed += 1
                continue
            component = labels == label
            component_distance = cv2.distanceTransform(component.astype(np.uint8), cv2.DIST_L2, 5)
            component_width = float(np.percentile(component_distance[component] * 2.0, 90)) if np.any(component) else 0.0
            if component_width > maximum_component_width:
                removed += 1
                continue
            touch = (cv2.dilate(component.astype(np.uint8), _kernel(9), iterations=1) > 0) & stable
            touch_count, _, touch_stats, _ = cv2.connectedComponentsWithStats(touch.astype(np.uint8), connectivity=8)
            anchors = sum(1 for index in range(1, touch_count) if int(touch_stats[index, cv2.CC_STAT_AREA]) >= 4)
            endpoint_touch = (cv2.dilate(component.astype(np.uint8), _kernel(11), iterations=1) > 0) & base_endpoint_mask
            endpoint_anchors = int(np.count_nonzero(endpoint_touch))
            # A symmetric difference is a completion candidate only when it
            # terminates at a real open end in the observed graph.  Mere contact
            # with any visible edge admitted leaf and wall fragments in A01.
            if endpoint_anchors >= 1 and (anchors >= 2 or area >= minimum_area * 4):
                component_score = endpoint_anchors * 3.0 + min(anchors, 5) + np.log1p(area) * 0.25
                component_records.append((component_score, area, anchors, endpoint_anchors, component))
            else:
                removed += 1
        # Do not accept the union of every symmetric difference.  Rank local
        # graph-attached components and keep a small budget.  This turns SRA into
        # a completion hypothesis instead of a second broad segmentation mask.
        component_budget = max(minimum_area * 4, int(np.count_nonzero(visible) * 0.10))
        selected_area = 0
        selected_components = 0
        for _score, area, anchors, endpoint_anchors, component in sorted(component_records, key=lambda item: item[0], reverse=True):
            if selected_area + area > component_budget:
                removed += 1
                continue
            candidate |= component
            selected_area += area
            selected_components += 1
            anchor_regions_total += anchors
            endpoint_anchors_total += endpoint_anchors
        merged = stable | candidate
        merged_skeleton = _skeleton(merged) > 0
        endpoints_after = int(np.count_nonzero(merged_skeleton & (_neighbor_count(merged_skeleton) == 1)))
        endpoint_gain = (base_endpoints - endpoints_after) / max(1, base_endpoints)
        endpoint_anchor_score = min(1.0, endpoint_anchors_total / 8.0)
        route_score = (
            symmetry * 0.25
            + max(-0.15, endpoint_gain) * 0.20
            + endpoint_anchor_score * 0.15
            + route_imbalances[name] * 0.40
        )
        route_results[name] = {
            "candidate": candidate,
            "symmetry": symmetry,
            "route_score": route_score,
            "candidate_pixels": int(np.count_nonzero(candidate)),
            "anchor_regions": int(anchor_regions_total),
            "endpoint_anchors": int(endpoint_anchors_total),
            "endpoints_after": endpoints_after,
            "endpoint_gain": endpoint_gain,
            "removed_components": removed,
            "selected_components": selected_components,
            "component_budget_pixels": component_budget,
            "directional_visible_imbalance": route_imbalances[name],
        }
    eligible_routes = [
        name for name, value in route_results.items()
        if value["symmetry"] >= 0.25
        and value["route_score"] >= 0.18
        and value["candidate_pixels"] >= minimum_area * 4
        and value["candidate_pixels"] <= int(np.count_nonzero(visible) * 0.18)
        and value["anchor_regions"] >= 1
        and value["endpoint_anchors"] >= 1
        and route_imbalances[name] >= 0.06
        and value["endpoint_gain"] >= (-0.25 if route_imbalances[name] >= 0.06 else -0.12)
        and base_endpoints <= 300
    ]
    best_name = max(eligible_routes or list(route_results), key=lambda name: route_results[name]["route_score"])
    best = route_results[best_name]
    accepted = bool(
        best["symmetry"] >= 0.25
        and best["route_score"] >= 0.18
        and best["candidate_pixels"] >= minimum_area * 4
        and best["candidate_pixels"] <= int(np.count_nonzero(visible) * 0.18)
        and best["anchor_regions"] >= 1
        and best["endpoint_anchors"] >= 1
        and route_imbalances[best_name] >= 0.06
        and best["endpoint_gain"] >= (-0.25 if route_imbalances[best_name] >= 0.06 else -0.12)
        and base_endpoints <= 300
    )
    proposed_candidate_pixels = int(best["candidate_pixels"])
    candidate = best["candidate"].copy() if accepted else np.zeros_like(visible)
    return candidate, {
        "enabled": True,
        "selected_transform": best_name,
        "symmetry_scores": {key: round(value["symmetry"], 4) for key, value in route_results.items()},
        "route_scores": {key: round(value["route_score"], 4) for key, value in route_results.items()},
        "selected_symmetry_score": round(float(best["symmetry"]), 4),
        "selected_route_score": round(float(best["route_score"]), 4),
        "acceptance_rule": "frame-normalised symmetry>=0.25, route_score>=0.18, missing-side/quadrant imbalance>=0.06, graph anchor, inferred area<=18%, endpoint loss<=12%, and pre-SRA endpoint count<=300",
        "accepted": accepted,
        "eligible_transforms": eligible_routes,
        "candidate_pixels": int(np.count_nonzero(candidate)),
        "proposed_candidate_pixels": proposed_candidate_pixels,
        "anchor_regions": int(best["anchor_regions"]),
        "endpoint_anchors": int(best["endpoint_anchors"]),
        "endpoints_before": base_endpoints,
        "endpoints_after": int(best["endpoints_after"]),
        "endpoint_gain": round(float(best["endpoint_gain"]), 4),
        "target_occlusion_pixels": int(np.count_nonzero(target_gate)),
        "minimum_component_area": minimum_area,
        "removed_candidate_components": int(best["removed_components"]),
        "selected_candidate_components": int(best["selected_components"]),
        "component_budget_pixels": int(best["component_budget_pixels"]),
        "dominant_visible_width_pixels": round(dominant_visible_width, 3),
        "sra_uniform_reconstruction_width_pixels": round(stable_width, 3),
        "maximum_inferred_component_width_pixels": round(maximum_component_width, 3),
        "route_endpoint_anchors": {key: int(value["endpoint_anchors"]) for key, value in route_results.items()},
        "route_endpoint_gains": {key: round(float(value["endpoint_gain"]), 4) for key, value in route_results.items()},
        "route_directional_visible_imbalances": {
            key: round(float(value["directional_visible_imbalance"]), 4) for key, value in route_results.items()
        },
        "quadrant_visible_pixels": quadrant_pixels,
        "quadrant_occlusion_pixels": quadrant_occlusion,
        "axis_occlusion_imbalances": {
            "vertical": round(vertical_occlusion_imbalance, 4),
            "horizontal": round(horizontal_occlusion_imbalance, 4),
        },
        "policy": "frame-normalised auxiliary layer; transfer only into the weaker axis half or diagonal quadrant under occlusion and graph-anchor gates",
    }


def _eco_binary_metrics(prediction: np.ndarray, reference: np.ndarray) -> dict[str, float]:
    pred = prediction.astype(bool)
    truth = reference.astype(bool)
    if pred.shape != truth.shape:
        truth = np.asarray(
            Image.fromarray((truth * 255).astype(np.uint8)).resize((pred.shape[1], pred.shape[0]), Image.Resampling.NEAREST)
        ) > 127
    tp = int(np.count_nonzero(pred & truth))
    fp = int(np.count_nonzero(pred & ~truth))
    fn = int(np.count_nonzero(~pred & truth))
    tn = int(np.count_nonzero(~pred & ~truth))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    return {
        "dice": round(2.0 * tp / max(1, 2 * tp + fp + fn), 6),
        "iou": round(tp / max(1, tp + fp + fn), 6),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "background_false_positive_rate": round(fp / max(1, fp + tn), 6),
    }


def _eco_diagnostic_reference_comparison(
    case_id: str,
    visible_mask: np.ndarray,
    completed_mask: np.ndarray | None = None,
    prior_eco_mask: np.ndarray | None = None,
) -> dict[str, Any]:
    """Compute a post-hoc diagnostic only after extraction is finished.

    The reference mask is never read by the ECO-Lattice extractor. This helper is
    deliberately isolated so that a browser result cannot accidentally tune itself
    to an individual manual annotation.
    """
    case = _clean_case_id(case_id)
    case_dir = ECO_GROUND_TRUTH_ROOT / case
    mask_path = case_dir / "manual_mask.png"
    if not mask_path.is_file():
        return {"available": False, "reason": "no_saved_manual_reference"}
    reference = np.asarray(Image.open(mask_path).convert("L")) > 127
    if not np.any(reference):
        return {"available": False, "reason": "manual_reference_is_blank"}
    status_path = case_dir / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.is_file() else {}
    result: dict[str, Any] = {
        "available": True,
        "role": "post_hoc_development_diagnostic_not_an_algorithm_input",
        "reference_status": status.get("status", "unknown"),
        "eco_lattice": _eco_binary_metrics(visible_mask, reference),
        "reference_definition": "modal_visible_material_only; fully occluded rods are not filled",
    }
    if completed_mask is not None:
        result["completed_hypothesis_against_visible_reference"] = _eco_binary_metrics(completed_mask, reference)
        result["completed_metric_warning"] = (
            "This score is diagnostic only: an amodal inferred layer is not definition-compatible "
            "with a visible-only manual reference."
        )
    if prior_eco_mask is not None:
        prior_metrics = _eco_binary_metrics(prior_eco_mask, reference)
        result["prior_eco_v01"] = prior_metrics
        result["delta_vs_prior_eco_v01"] = {
            key: round(result["eco_lattice"][key] - prior_metrics[key], 6)
            for key in ("dice", "iou", "precision", "recall", "background_false_positive_rate")
        }
    legacy_path = ECO_LEGACY_C_ROOT / case / "c6_mask.png"
    if legacy_path.is_file():
        legacy = np.asarray(Image.open(legacy_path).convert("L")) > 127
        legacy_metrics = _eco_binary_metrics(legacy, reference)
        eco_metrics = result["eco_lattice"]
        result["legacy_c6"] = legacy_metrics
        result["delta_vs_legacy_c6"] = {
            key: round(eco_metrics[key] - legacy_metrics[key], 6)
            for key in ("dice", "iou", "precision", "recall", "background_false_positive_rate")
        }
    return result


def run_eco_lattice_v01(rgb: np.ndarray, prompt: dict[str, Any] | None = None) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """ECO-Lattice v0.1: evidence-competitive visible lattice extraction.

    It replaces the old whole-window SAM starting point with physical rod evidence.
    No model weights, labels, clicks, brush strokes or manual masks enter this
    function.  The optional SRA completion layer is intentionally conservative and
    remains separate from the observed material mask.
    """
    prompt = prompt or {}
    stages: dict[str, np.ndarray] = {}
    details: dict[str, Any] = {}
    stage_times: dict[str, float] = {}
    height, width = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)

    tick = time.perf_counter()
    roi, roi_meta = _estimate_roi_mask(rgb, {})
    illumination, illumination_sigma = _eco_illumination_normalize(gray)
    stages["E0"] = roi
    details["E0"] = {
        "module": "free_roi_and_single_image_illumination_normalisation",
        **roi_meta,
        "retinex_sigma_pixels": round(illumination_sigma, 3),
        "policy": "automatic irregular ROI for development; no four-corner assumption",
    }
    stage_times["E0"] = time.perf_counter() - tick

    tick = time.perf_counter()
    edges = cv2.Canny(illumination, 30, 100) > 0
    edge_distance = cv2.distanceTransform((~edges).astype(np.uint8), cv2.DIST_L2, 3)
    vegetation = _eco_vegetation_mask(hsv)
    texture = _eco_texture_strength(gray)
    band_width = max(7, int(round(min(height, width) * 0.045)))
    inner_roi = cv2.erode(roi.astype(np.uint8), _kernel(band_width * 2 + 1), iterations=1) > 0
    frame_band = roi & ~inner_roi
    samples = lab[frame_band & ~vegetation].reshape(-1, 3).astype(np.float32)
    if len(samples) < 48:
        samples = lab[roi & ~vegetation].reshape(-1, 3).astype(np.float32)
    if len(samples) > 9000:
        samples = samples[np.linspace(0, len(samples) - 1, 9000).astype(int)]
    if len(samples) >= 48:
        cluster_count = min(3, max(1, len(samples) // 350))
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.2)
        cv2.setRNGSeed(20260831)
        _, _, centers = cv2.kmeans(samples, cluster_count, None, criteria, 6, cv2.KMEANS_PP_CENTERS)
    else:
        centers = np.asarray([np.median(lab[roi], axis=0) if np.any(roi) else np.median(lab.reshape(-1, 3), axis=0)], dtype=np.float32)
    material_distance = np.min(
        np.stack([np.linalg.norm(lab - center.reshape(1, 1, 3), axis=2) for center in centers]),
        axis=0,
    )
    sample_region = frame_band if np.any(frame_band) else roi
    material_limit = float(np.clip(np.percentile(material_distance[sample_region], 95), 10.0, 22.0))
    b_limit = float(np.percentile(lab[:, :, 2][roi], 50)) if np.any(roi) else float(np.percentile(lab[:, :, 2], 50))
    saturation_limit = float(np.clip(np.percentile(hsv[:, :, 1][roi], 70) if np.any(roi) else np.percentile(hsv[:, :, 1], 70), 42.0, 96.0))
    edge_distance_limit = max(4, int(round(min(height, width) * 0.012)))
    material_candidate = (
        roi
        & (material_distance <= material_limit)
        & (lab[:, :, 2] <= b_limit)
        & (hsv[:, :, 1] <= saturation_limit)
        & (edge_distance <= edge_distance_limit)
    )
    e1 = cv2.morphologyEx(material_candidate.astype(np.uint8), cv2.MORPH_CLOSE, _kernel(5), iterations=1) > 0
    stages["E1"] = e1
    details["E1"] = {
        "module": "frame_constrained_material_and_paired_edge_rod_candidates",
        "material_cluster_centers_lab": [[round(float(value), 2) for value in center] for center in centers],
        "material_distance_limit": round(material_limit, 3),
        "lab_b_limit": round(b_limit, 3),
        "saturation_limit": round(saturation_limit, 3),
        "edge_distance_limit_pixels": edge_distance_limit,
        "policy": "image_internal_material prototype plus narrow edge-neighbourhood rod evidence",
    }
    stage_times["E1"] = time.perf_counter() - tick

    tick = time.perf_counter()
    distance = cv2.distanceTransform(e1.astype(np.uint8), cv2.DIST_L2, 5)
    skeleton_e1 = _skeleton(e1) > 0
    width_values = distance[skeleton_e1] * 2.0
    if width_values.size >= 12:
        dominant_width = float(np.median(width_values))
        width_limit = float(np.clip(np.percentile(width_values, 97), max(8.0, dominant_width * 1.45), max(24.0, dominant_width * 4.0)))
        wide_core = distance > width_limit / 2.0
        e2 = e1 & ~wide_core
    else:
        dominant_width = 0.0
        width_limit = 0.0
        wide_core = np.zeros_like(e1, dtype=bool)
        e2 = e1.copy()
    e2 = cv2.morphologyEx(e2.astype(np.uint8), cv2.MORPH_CLOSE, _kernel(3), iterations=1) > 0
    stages["E2"] = e2
    details["E2"] = {
        "module": "image_internal_rod_width_self_calibration",
        "dominant_width_pixels": round(dominant_width, 3),
        "upper_width_limit_pixels": round(width_limit, 3),
        "wide_core_pixels_reclassified_uncertain": int(np.count_nonzero(wide_core & e1)),
        "policy": "soft width constraint; broad regions are not treated as confirmed rods",
    }
    stage_times["E2"] = time.perf_counter() - tick

    tick = time.perf_counter()
    texture_threshold = float(np.percentile(texture[roi], 86)) if np.any(roi) else float(np.percentile(texture, 86))
    rough_nonmaterial = (texture >= texture_threshold) & (material_distance > material_limit * 0.78)
    interference = vegetation | rough_nonmaterial
    # Competition occurs only where the candidate itself is weak. This prevents a
    # leaf seen through an opening from erasing an actually visible lattice bar.
    weak_material = material_distance > material_limit * 0.85
    weak_edge = edge_distance > max(1.0, edge_distance_limit * 0.75)
    reject = e2 & interference & weak_material & weak_edge
    e3 = e2 & ~reject
    stages["E3"] = e3
    details["E3"] = {
        "module": "rod_interference_evidence_competition",
        "vegetation_interference_pixels": int(np.count_nonzero(vegetation & roi)),
        "rough_interference_pixels": int(np.count_nonzero(rough_nonmaterial & roi)),
        "candidate_pixels_rejected": int(np.count_nonzero(reject)),
        "texture_threshold": round(texture_threshold, 3),
        "policy": "interference can veto weak rod evidence but cannot erase strong visible material evidence",
    }
    stage_times["E3"] = time.perf_counter() - tick

    tick = time.perf_counter()
    e4, minimum_area, removed_components = _eco_remove_tiny_components(e3)
    e4 &= roi
    visible_skeleton = _skeleton(e4) > 0
    stages["E4"] = e4
    details["E4"] = {
        "module": "visible_topology_selection",
        "minimum_component_area": minimum_area,
        "removed_tiny_components": removed_components,
        "visible_skeleton_pixels": int(np.count_nonzero(visible_skeleton)),
        "policy": "retain observed topology only; no global whole-window object mask is introduced",
    }
    stage_times["E4"] = time.perf_counter() - tick

    tick = time.perf_counter()
    bridge, bridge_meta = _eco_conservative_bridges(e4, e1, interference)
    # E5 is deliberately a candidate layer: it is visualised but never becomes
    # white/observed material in E6. Symmetry/repetition assistance can feed this
    # layer in a later controlled experiment without changing the visible evidence.
    e5 = e4 | bridge
    stages["E5"] = e5
    details["E5"] = {
        "module": "evidence_constrained_candidate_bridge_layer",
        **bridge_meta,
        "symmetry_repetition_assistance": {
            "enabled": bool(prompt.get("enable_sra", False)),
            "status": "reserved_for_high_confidence_candidate_bridges_only",
            "note": "SRA never writes a hidden segment into M_visible in this version.",
        },
    }
    stage_times["E5"] = time.perf_counter() - tick

    tick = time.perf_counter()
    # The final build-ready evidence mask contains observed pixels only. Bridge
    # candidates remain an auditable separate graph layer.
    e6 = e4.copy()
    uncertain = (e1 & ~e4) | bridge
    stages["E6"] = e6
    details["E6"] = {
        "module": "layered_visible_material_and_graph_output",
        "visible_pixels": int(np.count_nonzero(e6)),
        "uncertain_or_inferred_pixels": int(np.count_nonzero(uncertain)),
        "candidate_bridge_pixels": int(np.count_nonzero(bridge)),
        "policy": "M_visible is build-ready observed evidence; G_bridge is excluded unless later accepted in a separate reconstruction decision",
    }
    stage_times["E6"] = time.perf_counter() - tick

    for name, stage_mask in stages.items():
        details[name]["metrics"] = _structural_metrics(stage_mask, rgb)
        details[name]["stage_duration_seconds"] = round(stage_times[name], 4)
    metadata = {
        "method": "ECO-Lattice evidence-competitive occlusion-aware lattice extraction",
        "scientific_name_zh": "基于证据竞争与可见性约束的传统窗棂杆件提取",
        "algorithm_version": "eco_lattice_v0.1_development",
        "definition": "A zero-training visible-material extractor based on free ROI, illumination normalisation, frame-constrained material/edge rod evidence, image-internal width calibration, interference competition, visible topology selection and separately auditable bridge candidates.",
        "training_or_finetuning": False,
        "manual_brush": False,
        "manual_box_or_points": False,
        "manual_reference_used_for_extraction": False,
        "stage_order": list(stages),
        "stages": details,
        "_artifact_masks": {
            "interference": interference,
            "visible": e6,
            "uncertain": uncertain,
            "bridge": bridge,
            "skeleton": visible_skeleton,
            "roi": roi,
        },
        "total_stage_duration_seconds": round(sum(stage_times.values()), 4),
        "development_scope": "single-image prototype; not yet frozen for formal 30-image evaluation",
    }
    return stages, metadata


def run_eco_lattice(rgb: np.ndarray, prompt: dict[str, Any] | None = None) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """ECO-Lattice v0.3: observed extraction plus accepted completion hypothesis.

    Manual references never enter this function.  The visible-material layer is
    solved first; CCC, TGC and SRA then produce auditable candidate graphs that
    remain separate from the observed mask.  CCF-DB is explicitly disabled until
    an independent, leakage-free component library exists.
    """
    prompt = prompt or {}
    stages: dict[str, np.ndarray] = {}
    details: dict[str, Any] = {}
    stage_times: dict[str, float] = {}
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    tick = time.perf_counter()
    roi, frame, frame_observed, roi_meta = _eco_frame_first_roi(rgb)
    frame_inferred = frame & ~frame_observed
    _, illumination_sigma = _eco_illumination_normalize(gray)
    stages["E0"] = roi
    details["E0"] = {
        "module": "frame_first_roi_and_illumination_stabilisation",
        **roi_meta,
        "retinex_sigma_pixels": round(illumination_sigma, 3),
        "policy": "detect square/rectangle/circle/ellipse boundary first, lock the internal domain, then segment ornament",
    }
    stage_times["E0"] = time.perf_counter() - tick

    structural_mode, nonrod_visible, nonrod_interference, nonrod_uncertain, structural_mode_meta = _eco_nonrod_structural_branch(
        rgb, roi, frame, frame_observed, str(roi_meta.get("frame_shape") or "")
    )
    rod_like_mode = structural_mode in {"uniform_rod_lattice", "occluded_uniform_rod_lattice"}

    tick = time.perf_counter()
    visible, interference, occluder, uncertain, evidence_meta = _eco_multiscale_visible_evidence(rgb, roi)
    # The graph-cut branch is intentionally paired with the earlier
    # material/width/interference-competition branch.  They fail differently:
    # graph-cut is strong on compact circular lattices (G02), while the explicit
    # competition branch preserves dark continuous rods against plants and roof
    # texture (P02/P04/T01).  The router uses only output plausibility, never a
    # manual mask or case id.
    prior_stages, prior_metadata = run_eco_lattice_v01(rgb, {})
    prior_artifacts = prior_metadata.get("_artifact_masks", {})
    prior_visible = prior_artifacts.get("visible", prior_stages["E6"]).astype(bool)
    prior_interference = prior_artifacts.get("interference", interference).astype(bool)
    prior_uncertain = prior_artifacts.get("uncertain", np.zeros_like(visible, dtype=bool)).astype(bool)

    def branch_quality(mask: np.ndarray) -> dict[str, float]:
        height_q, width_q = mask.shape
        left_q = int(np.count_nonzero(mask[:, : width_q // 2]))
        right_q = int(np.count_nonzero(mask[:, width_q // 2 :]))
        top_q = int(np.count_nonzero(mask[: height_q // 2, :]))
        bottom_q = int(np.count_nonzero(mask[height_q // 2 :, :]))
        return {
            "coverage": float(np.mean(mask)),
            "left_right_imbalance": abs(left_q - right_q) / max(1, left_q + right_q),
            "top_bottom_imbalance": abs(top_q - bottom_q) / max(1, top_q + bottom_q),
        }

    graphcut_quality = branch_quality(visible)
    competition_quality = branch_quality(prior_visible)
    graphcut_collapse = graphcut_quality["coverage"] < competition_quality["coverage"] * 0.45
    graphcut_one_sided = max(
        graphcut_quality["left_right_imbalance"], graphcut_quality["top_bottom_imbalance"]
    ) > 0.85 and competition_quality["coverage"] > graphcut_quality["coverage"] * 1.25
    selected_visible_branch = "material_width_interference_competition" if (graphcut_collapse or graphcut_one_sided) else "multiscale_graphcut"
    if selected_visible_branch == "material_width_interference_competition":
        visible = prior_visible & roi
        interference = prior_interference & roi
        uncertain = prior_uncertain & roi
        # Rebuild the occlusion admission layer around the selected observed
        # graph.  Green/rough background in a normal opening is not automatically
        # an occlusion; it must occur near an observed open end or form a dense
        # foreground field close to the structure.
        selected_skeleton = _skeleton(visible) > 0
        selected_endpoints = selected_skeleton & (_neighbor_count(selected_skeleton) == 1)
        endpoint_radius = max(9, int(round(min(visible.shape) * 0.035)) | 1)
        endpoint_zone = cv2.dilate(selected_endpoints.astype(np.uint8), _kernel(endpoint_radius), iterations=1) > 0
        density_sigma = max(5.0, float(min(visible.shape)) * 0.028)
        interference_density = cv2.GaussianBlur(interference.astype(np.float32), (0, 0), density_sigma)
        density_values = interference_density[roi]
        density_threshold = max(0.10, float(np.percentile(density_values, 74)) if density_values.size else 0.10)
        dense_interference = interference_density >= density_threshold
        near_radius = max(15, int(round(min(visible.shape) * 0.085)) | 1)
        near_structure = cv2.dilate(visible.astype(np.uint8), _kernel(near_radius), iterations=1) > 0
        occluder = ((interference & endpoint_zone) | (dense_interference & near_structure)) & roi
        occluder = cv2.morphologyEx(occluder.astype(np.uint8), cv2.MORPH_CLOSE, _kernel(11), iterations=1) > 0
        uncertain = (uncertain | occluder) & roi
    routed_occluder = occluder.copy()
    if structural_mode != "uniform_rod_lattice" and nonrod_visible is not None:
        visible = nonrod_visible & roi
        interference = (nonrod_interference if nonrod_interference is not None else np.zeros_like(visible)) & roi
        uncertain = (nonrod_uncertain if nonrod_uncertain is not None else np.zeros_like(visible)) & roi
        occluder = (
            routed_occluder & roi
            if structural_mode == "occluded_uniform_rod_lattice"
            else np.zeros_like(visible, dtype=bool)
        )
        selected_visible_branch = structural_mode
    # Obstacle exclusion must also apply after branch routing.  The legacy
    # competition branch can preserve green leaf fragments when they touch a
    # valid bar; such fragments must not become the source of a later SRA copy.
    selected_hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    routed_vegetation = _eco_vegetation_mask(selected_hsv) & roi
    # Hue alone is unsafe: pale grey stone photographed through green reflected
    # light can fall into the vegetation hue interval. Only strongly saturated
    # vegetation is deleted from the observed layer; weaker cues remain as
    # interference evidence for the completion routes.
    hard_vegetation = routed_vegetation & (selected_hsv[:, :, 1] >= 72)
    vegetation_removed_after_routing = int(np.count_nonzero(visible & hard_vegetation & ~frame_observed))
    visible &= ~hard_vegetation | frame_observed
    interference |= routed_vegetation & roi & ~frame
    solid_occluder = np.zeros_like(visible, dtype=bool)
    solid_occluder_meta: dict[str, Any] = {"enabled": False, "reason": "structural_mode_not_occluded_rods"}
    if structural_mode == "occluded_uniform_rod_lattice":
        solid_occluder, solid_occluder_meta = _eco_boundary_solid_occluder(rgb, interference, roi)
        occluder |= solid_occluder
        visible &= ~solid_occluder | frame_observed
        interference |= solid_occluder
        uncertain |= solid_occluder
    extension_imbalance = max(
        graphcut_quality["left_right_imbalance"], graphcut_quality["top_bottom_imbalance"]
    )
    if structural_mode != "uniform_rod_lattice":
        extension_skip_reason = "structural_mode_not_uniform_rods"
    elif selected_visible_branch != "multiscale_graphcut":
        extension_skip_reason = "selected_branch_not_multiscale_graphcut"
    else:
        extension_skip_reason = "no_severe_axis_imbalance"
    rod_extension_meta: dict[str, Any] = {"enabled": False, "reason": extension_skip_reason}
    if (
        structural_mode == "uniform_rod_lattice"
        and selected_visible_branch == "multiscale_graphcut"
        and extension_imbalance >= 0.20
    ):
        rod_extension, rod_extension_meta = _eco_illumination_invariant_rod_extension(rgb, visible, roi)
        visible |= rod_extension
        uncertain &= ~rod_extension
    # The observed part of the parametric boundary is architectural evidence.
    # The unsupported remainder remains an inferred frame layer and is never
    # silently relabelled as a directly observed pixel.
    visible = (visible | frame_observed) & roi
    interference &= roi & ~frame
    occluder &= roi & ~frame_observed
    uncertain = (uncertain | (frame & ~frame_observed)) & roi
    weak_evidence = (visible | uncertain) & roi
    # Completion routes need a cleaner source than the observed audit layer.
    # Low-chroma consistency suppresses leaf/flower contours before mirroring or
    # gap closing; it does not erase them from diagnostics and is learned from
    # this image rather than from a case-specific colour value.
    saturation = selected_hsv[:, :, 1].astype(np.float32)
    saturation_samples = saturation[visible & ~routed_vegetation & ~frame]
    completion_saturation_limit = float(np.clip(
        (np.percentile(saturation_samples, 72) + 10.0) if saturation_samples.size else 70.0,
        42.0,
        68.0,
    ))
    completion_source = visible & ((saturation <= completion_saturation_limit) | frame_observed)
    # Match the completion source to material modes observed on the architectural
    # boundary. This rejects neutral tree trunks, shadows and masonry edges that
    # survive a saturation test but do not share the frame material.
    completion_lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    frame_sample_zone = cv2.dilate(frame_observed.astype(np.uint8), _kernel(7), iterations=1) > 0
    frame_samples = completion_lab[visible & frame_sample_zone].reshape(-1, 3)
    material_centers: list[list[float]] = []
    completion_material_limit = 34.0
    obstacle_material_removed = 0
    if len(frame_samples) >= 40:
        if len(frame_samples) > 8000:
            frame_samples = frame_samples[np.linspace(0, len(frame_samples) - 1, 8000).astype(int)]
        cluster_count = min(3, max(1, len(frame_samples) // 1000))
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.3)
        cv2.setRNGSeed(6082026)
        _, _, centers = cv2.kmeans(frame_samples.astype(np.float32), cluster_count, None, criteria, 4, cv2.KMEANS_PP_CENTERS)
        chroma = np.linalg.norm(centers[:, 1:3] - 128.0, axis=1)
        centers = centers[np.argsort(chroma)[: min(2, len(centers))]]
        material_distance = np.min(
            np.stack([np.linalg.norm(completion_lab - center.reshape(1, 1, 3), axis=2) for center in centers]),
            axis=0,
        )
        frame_distances = material_distance[visible & frame_sample_zone]
        completion_material_limit = float(np.clip(np.percentile(frame_distances, 88) + 5.0, 18.0, 34.0)) if frame_distances.size else 30.0
        completion_source &= material_distance <= completion_material_limit
        obstacle_material_mismatch = visible & interference & (material_distance > completion_material_limit * 1.30) & ~frame
        obstacle_material_removed = int(np.count_nonzero(obstacle_material_mismatch))
        visible &= ~obstacle_material_mismatch
        completion_source &= visible
        material_centers = [[round(float(value), 2) for value in center] for center in centers]
    completion_source, _completion_minimum_area, _completion_removed = _eco_remove_tiny_components(completion_source)
    completion_weak_evidence = (completion_source | (uncertain & (saturation <= completion_saturation_limit * 1.18))) & roi
    weak_evidence = (visible | uncertain) & roi
    stages["E1"] = weak_evidence
    details["E1"] = {
        "module": "dual_branch_visible_rod_evidence_router",
        **evidence_meta,
        "selected_visible_branch": selected_visible_branch,
        "graphcut_branch_quality": {key: round(value, 6) for key, value in graphcut_quality.items()},
        "competition_branch_quality": {key: round(value, 6) for key, value in competition_quality.items()},
        "graphcut_collapse_detected": bool(graphcut_collapse),
        "graphcut_one_sided_failure_detected": bool(graphcut_one_sided),
        "vegetation_pixels_removed_after_routing": vegetation_removed_after_routing,
        "completion_source_pixels": int(np.count_nonzero(completion_source)),
        "completion_source_saturation_limit": round(completion_saturation_limit, 3),
        "completion_source_material_centers_lab": material_centers,
        "completion_source_material_distance_limit": round(completion_material_limit, 3),
        "obstacle_material_mismatch_pixels_removed": obstacle_material_removed,
        "structural_mode": structural_mode,
        "structural_mode_diagnostic": structural_mode_meta,
        "illumination_invariant_rod_extension": rod_extension_meta,
        "policy": "route between multiscale graph-cut and explicit material/width/interference competition using output plausibility only; no manual reference",
    }
    stage_times["E1"] = time.perf_counter() - tick

    tick = time.perf_counter()
    stages["E2"] = visible
    details["E2"] = {
        "module": "rod_interference_competition_and_occluder_gate",
        "visible_pixels": int(np.count_nonzero(visible)),
        "interference_pixels": int(np.count_nonzero(interference)),
        "occluder_pixels": int(np.count_nonzero(occluder)),
        "uncertain_pixels": int(np.count_nonzero(uncertain)),
        "frame_observed_pixels": int(np.count_nonzero(frame_observed)),
        "outside_frame_foreground_pixels": int(np.count_nonzero(visible & ~roi)),
        "boundary_solid_occluder": solid_occluder_meta,
        "policy": "background seen through a normal opening is not bridge-eligible; outside-frame foreground is forbidden",
    }
    stage_times["E2"] = time.perf_counter() - tick

    tick = time.perf_counter()
    if rod_like_mode:
        continuity, continuity_meta = _eco_directional_continuity_candidates(
            completion_source, completion_weak_evidence, occluder, roi
        )
        ccc, ccc_meta = _eco_conservative_bridges(
            completion_source | continuity, completion_weak_evidence, occluder
        )
        ccc |= continuity
    else:
        continuity = np.zeros_like(visible, dtype=bool)
        ccc = np.zeros_like(visible, dtype=bool)
        continuity_meta = {"enabled": False, "reason": f"not_applicable_to_{structural_mode}"}
        ccc_meta = {"enabled": False, "reason": f"not_applicable_to_{structural_mode}"}
    stages["E3"] = visible | ccc
    details["E3"] = {
        "module": "directional_continuity_plus_ccc_candidates",
        **ccc_meta,
        "directional_continuity": continuity_meta,
        "policy": "orientation-aware fragmentation repair plus short two-endpoint candidates; inferred layer only",
    }
    stage_times["E3"] = time.perf_counter() - tick

    tick = time.perf_counter()
    if rod_like_mode:
        tgc, tgc_meta = _eco_topology_graph_candidates(
            completion_source | ccc, completion_weak_evidence, occluder
        )
    else:
        tgc = np.zeros_like(visible, dtype=bool)
        tgc_meta = {"enabled": False, "reason": f"not_applicable_to_{structural_mode}"}
    stages["E4"] = visible | ccc | tgc
    details["E4"] = {
        "module": "tgc_topology_graph_candidates",
        **tgc_meta,
    }
    stage_times["E4"] = time.perf_counter() - tick

    tick = time.perf_counter()
    if not rod_like_mode:
        sra = np.zeros_like(visible, dtype=bool)
        sra_meta = {"enabled": False, "reason": f"not_applicable_to_{structural_mode}"}
    elif bool(prompt.get("disable_sra", False)):
        sra = np.zeros_like(visible)
        sra_meta: dict[str, Any] = {"enabled": False, "reason": "disabled_by_ablation_prompt"}
    else:
        sra, sra_meta = _eco_sra_candidates(completion_source | ccc | tgc, occluder, uncertain & (saturation <= completion_saturation_limit * 1.18), roi)
    solid_occluder_sra = np.zeros_like(visible, dtype=bool)
    solid_occluder_sra_meta: dict[str, Any] = {"enabled": False, "reason": "no_boundary_solid_occluder"}
    if structural_mode == "occluded_uniform_rod_lattice" and np.any(solid_occluder):
        # Build the source only from neutral, sufficiently luminous observed
        # architectural material.  Mirroring the complete visible mask would
        # copy foliage/texture fragments into the rock and create a false mesh.
        source_hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        source_gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        source_vegetation = _eco_vegetation_mask(source_hsv)
        source_structure = (
            (visible | ccc | tgc)
            & ~source_vegetation
            & (source_hsv[:, :, 1] <= 82)
            & (source_gray >= 82)
        )
        source_structure = cv2.morphologyEx(
            source_structure.astype(np.uint8), cv2.MORPH_CLOSE, _kernel(3), iterations=1
        ) > 0
        source_structure, _, _ = _eco_remove_tiny_components(source_structure)
        source_anchor = cv2.dilate(frame_observed.astype(np.uint8), _kernel(17), iterations=1) > 0
        labels_count, labels, stats, _ = cv2.connectedComponentsWithStats(
            source_structure.astype(np.uint8), 8
        )
        anchored_source = np.zeros_like(source_structure)
        for label in range(1, labels_count):
            component = labels == label
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area >= 20 and np.count_nonzero(component & source_anchor) >= 2:
                anchored_source |= component
        if np.count_nonzero(anchored_source) >= 120:
            source_structure = anchored_source
        mirrored_source = np.fliplr(source_structure)
        mirrored_skeleton = _skeleton(mirrored_source) > 0
        solid_target = cv2.dilate(solid_occluder.astype(np.uint8), _kernel(9), iterations=1) > 0
        core = mirrored_skeleton & solid_target & ~visible
        source_skeleton = _skeleton(source_structure) > 0
        distance = cv2.distanceTransform(source_structure.astype(np.uint8), cv2.DIST_L2, 5)
        source_widths = distance[source_skeleton] * 2.0
        reconstruction_width = float(np.clip(np.median(source_widths), 4.0, 16.0)) if source_widths.size else 6.0
        solid_occluder_sra = cv2.dilate(
            core.astype(np.uint8), _kernel(max(3, int(round(reconstruction_width)) | 1)), iterations=1
        ) > 0
        solid_occluder_sra &= solid_target & ~visible & roi
        solid_occluder_sra, minimum_sra_area, removed_sra = _eco_remove_tiny_components(solid_occluder_sra)
        sra |= solid_occluder_sra
        sra_meta["accepted"] = bool(np.any(sra))
        sra_meta["selected_transform"] = "vertical_mirror_into_solid_occluder"
        sra_meta["candidate_pixels"] = int(np.count_nonzero(sra))
        solid_occluder_sra_meta = {
            "enabled": True,
            "candidate_pixels": int(np.count_nonzero(solid_occluder_sra)),
            "reconstruction_width_pixels": round(reconstruction_width, 3),
            "minimum_component_area": minimum_sra_area,
            "removed_tiny_components": removed_sra,
            "policy": "copy only the opposite-side observed graph into a separately detected solid foreground occluder; never infer from the rock texture itself",
        }
    stages["E5"] = visible | ccc | tgc | sra
    details["E5"] = {
        "module": "sra_symmetry_repetition_auxiliary_candidates",
        **sra_meta,
        "solid_occluder_sra": solid_occluder_sra_meta,
        "ccf_db": {
            "enabled": False,
            "reason": "no_independent_leakage_free_component_database",
            "paper_role": "optional future route rather than a claimed implemented module",
        },
    }
    stage_times["E5"] = time.perf_counter() - tick

    tick = time.perf_counter()
    # A closed frame is mandatory for the downstream 2.5D model. Unsupported
    # frame segments are therefore explicit orange hypotheses, not observed cyan.
    bridge = (frame_inferred | ccc | tgc | sra) & ~visible & roi
    completed = visible | bridge
    final_uncertain = (uncertain | bridge) & roi
    visible_skeleton = _skeleton(visible) > 0
    stages["E6"] = completed
    details["E6"] = {
        "module": "accepted_bridge_fusion_and_completed_hypothesis",
        "visible_pixels": int(np.count_nonzero(visible)),
        "ccc_candidate_pixels": int(np.count_nonzero(ccc)),
        "tgc_candidate_pixels": int(np.count_nonzero(tgc)),
        "sra_candidate_pixels": int(np.count_nonzero(sra)),
        "frame_inferred_pixels": int(np.count_nonzero(frame_inferred & ~visible)),
        "continuity_candidate_pixels": int(np.count_nonzero(continuity)),
        "bridge_candidate_pixels": int(np.count_nonzero(bridge)),
        "completed_pixels": int(np.count_nonzero(completed)),
        "completion_gain_pixels": int(np.count_nonzero(bridge)),
        "completion_gain_ratio_vs_visible": round(float(np.count_nonzero(bridge) / max(1, np.count_nonzero(visible))), 6),
        "uncertain_pixels": int(np.count_nonzero(final_uncertain)),
        "route_policy": "closed parametric frame first; directional/CCC short gaps; TGC medium graph gaps; SRA quadrant/axis auxiliary completion",
        "output_policy": "M_completed=M_visible union accepted G_bridge; observed and inferred layers remain independently auditable",
    }
    stage_times["E6"] = time.perf_counter() - tick

    for name, stage_mask in stages.items():
        details[name]["metrics"] = _structural_metrics(stage_mask, rgb)
        details[name]["stage_duration_seconds"] = round(stage_times[name], 4)
    metadata = {
        "method": "ECO-Lattice routed multi-prior occlusion-aware lattice extraction",
        "scientific_name_zh": "基于可见证据竞争、遮挡准入与多先验路由的传统窗棂结构提取",
        "algorithm_version": "eco_lattice_v0.8_occluder_illumination_router_prototype",
        "definition": "Frame-first zero-training extraction with structural-mode routing, boundary-entering solid-occluder admission, occluder-targeted symmetry completion, and illumination-invariant rod continuation across black/grey/white material changes.",
        "training_or_finetuning": False,
        "manual_brush": False,
        "manual_box_or_points": False,
        "manual_reference_used_for_extraction": False,
        "implemented_routes": ["CCC", "TGC", "SRA", "solid-occluder SRA", "illumination-invariant rod extension"],
        "disabled_routes": ["CCF-DB"],
        "stage_order": list(stages),
        "stages": details,
        "_artifact_masks": {
            "interference": interference,
            "occluder": occluder,
            "visible": visible,
            "completed": completed,
            "uncertain": final_uncertain,
            "ccc": ccc,
            "continuity": continuity,
            "tgc": tgc,
            "sra": sra,
            "bridge": bridge,
            "skeleton": visible_skeleton,
            "roi": roi,
            "frame": frame,
            "frame_observed": frame_observed,
            "frame_inferred": frame_inferred,
            "completion_source": completion_source,
            "router_prior_visible": prior_visible,
        },
        "total_stage_duration_seconds": round(sum(stage_times.values()), 4),
        "development_scope": "single-image development diagnostic; not frozen for formal paper evaluation",
    }
    return stages, metadata


def _save_eco_lattice_result(
    case_id: str,
    rgb: np.ndarray,
    stages: dict[str, np.ndarray],
    metadata: dict[str, Any],
    artifacts: dict[str, np.ndarray],
) -> Path:
    run_id = time.strftime("%Y%m%d_%H%M%S") + f"_{time.time_ns() % 1_000_000:06d}"
    output_dir = ECO_DEVELOPMENT_ROOT / _clean_case_id(case_id) / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "source.png").write_bytes(_png_bytes(rgb))
    for stage_name, stage_mask in stages.items():
        stem = stage_name.lower()
        (output_dir / f"{stem}_mask.png").write_bytes(_png_bytes(_mask_png(stage_mask)))
        (output_dir / f"{stem}_overlay.png").write_bytes(_png_bytes(_overlay(rgb, stage_mask)))
    for artifact_name in ("interference", "occluder", "visible", "completed", "uncertain", "frame", "frame_observed", "frame_inferred", "continuity", "ccc", "tgc", "sra", "bridge", "skeleton", "roi"):
        artifact = artifacts.get(artifact_name, np.zeros(stages["E6"].shape, dtype=bool))
        (output_dir / f"{artifact_name}.png").write_bytes(_png_bytes(_mask_png(artifact)))
    (output_dir / "completed_overlay.png").write_bytes(
        _png_bytes(_completion_overlay(rgb, artifacts.get("visible", stages["E6"]), artifacts.get("bridge", np.zeros_like(stages["E6"], dtype=bool))))
    )
    (output_dir / "obstacle_diagnostic_overlay.png").write_bytes(
        _png_bytes(
            _obstacle_diagnostic_overlay(
                rgb,
                artifacts.get("visible", stages["E6"]),
                artifacts.get("interference", np.zeros_like(stages["E6"], dtype=bool)),
                artifacts.get("occluder", np.zeros_like(stages["E6"], dtype=bool)),
            )
        )
    )
    confidence = np.zeros(stages["E6"].shape, dtype=np.uint8)
    confidence[artifacts.get("interference", np.zeros_like(stages["E6"], dtype=bool))] = 45
    confidence[artifacts.get("uncertain", np.zeros_like(stages["E6"], dtype=bool))] = 135
    confidence[artifacts.get("bridge", np.zeros_like(stages["E6"], dtype=bool))] = 160
    confidence[artifacts.get("visible", stages["E6"])] = 255
    (output_dir / "confidence_map.png").write_bytes(_png_bytes(confidence))
    diagnostic = metadata.get("diagnostic_reference_comparison", {"available": False})
    (output_dir / "diagnostic_reference_comparison.json").write_text(
        json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    topology = _structural_metrics(stages["E6"], rgb)
    topology.update({
        "visible_pixels": int(np.count_nonzero(artifacts.get("visible", stages["E6"]))),
        "completed_pixels": int(np.count_nonzero(artifacts.get("completed", stages["E6"]))),
        "uncertain_pixels": int(np.count_nonzero(artifacts.get("uncertain", np.zeros_like(stages["E6"], dtype=bool)))),
        "bridge_candidate_pixels": int(np.count_nonzero(artifacts.get("bridge", np.zeros_like(stages["E6"], dtype=bool)))),
        "ccc_candidate_pixels": int(np.count_nonzero(artifacts.get("ccc", np.zeros_like(stages["E6"], dtype=bool)))),
        "continuity_candidate_pixels": int(np.count_nonzero(artifacts.get("continuity", np.zeros_like(stages["E6"], dtype=bool)))),
        "tgc_candidate_pixels": int(np.count_nonzero(artifacts.get("tgc", np.zeros_like(stages["E6"], dtype=bool)))),
        "sra_candidate_pixels": int(np.count_nonzero(artifacts.get("sra", np.zeros_like(stages["E6"], dtype=bool)))),
        "frame_pixels": int(np.count_nonzero(artifacts.get("frame", np.zeros_like(stages["E6"], dtype=bool)))),
        "note": "M_visible and G_bridge are deliberately stored as separate layers.",
    })
    (output_dir / "topology.json").write_text(json.dumps(topology, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "run.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_dir


def _save_result(method: str, case_id: str, rgb: np.ndarray, mask: np.ndarray, metadata: dict[str, Any]) -> Path:
    method_folder = {
        "sam_b": "06_开放词汇SAM2基础分割_30张",
        "c_rule": "07_传统规则自动分割基线_30张",
    }[method]
    run_id = time.strftime("%Y%m%d_%H%M%S") + f"_{time.time_ns() % 1_000_000:06d}"
    output_dir = EXPERIMENT_ROOT / method_folder / _clean_case_id(case_id) / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "source.png").write_bytes(_png_bytes(rgb))
    (output_dir / "mask.png").write_bytes(_png_bytes(_mask_png(mask)))
    (output_dir / "overlay.png").write_bytes(_png_bytes(_overlay(rgb, mask)))
    (output_dir / "run.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_dir


def _save_c_sam_result(
    case_id: str,
    rgb: np.ndarray,
    stages: dict[str, np.ndarray],
    metadata: dict[str, Any],
    artifacts: dict[str, np.ndarray] | None = None,
) -> Path:
    run_id = time.strftime("%Y%m%d_%H%M%S") + f"_{time.time_ns() % 1_000_000:06d}"
    output_dir = EXPERIMENT_ROOT / "08_障碍感知与拓扑反馈窗棂分割_30张" / _clean_case_id(case_id) / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "source.png").write_bytes(_png_bytes(rgb))
    for stage_name, stage_mask in stages.items():
        stem = stage_name.lower()
        (output_dir / f"{stem}_mask.png").write_bytes(_png_bytes(_mask_png(stage_mask)))
        (output_dir / f"{stem}_overlay.png").write_bytes(_png_bytes(_overlay(rgb, stage_mask)))
    artifacts = artifacts or {}
    obstacle = artifacts.get("obstacle", np.zeros(stages["C6"].shape, dtype=bool))
    observed = artifacts.get("observed", stages["C4"])
    inferred = artifacts.get("inferred", stages["C5"] & ~stages["C4"])
    confidence = np.zeros(stages["C6"].shape, dtype=np.uint8)
    confidence[stages["C6"]] = 205
    confidence[observed] = 255
    confidence[inferred] = 145
    skeleton = _skeleton(stages["C6"]) > 0
    (output_dir / "obstacle_mask.png").write_bytes(_png_bytes(_mask_png(obstacle)))
    (output_dir / "observed_mask.png").write_bytes(_png_bytes(_mask_png(observed)))
    (output_dir / "inferred_mask.png").write_bytes(_png_bytes(_mask_png(inferred)))
    (output_dir / "confidence_map.png").write_bytes(_png_bytes(confidence))
    (output_dir / "skeleton.png").write_bytes(_png_bytes(_mask_png(skeleton)))
    topology = _structural_metrics(stages["C6"], rgb)
    topology.update({
        "observed_pixels": int(observed.sum()),
        "inferred_pixels": int(inferred.sum()),
        "obstacle_pixels": int(obstacle.sum()),
        "note": "Pixel skeleton summary; full node-edge graph is generated in the downstream 3D reconstruction platform.",
    })
    (output_dir / "topology.json").write_text(json.dumps(topology, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "run.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_dir


def run_segmentation_method(method: str, case_id: str, image_bytes: bytes, prompt: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    rgb = _read_rgb(image_bytes)
    if method == "eco_lattice":
        stages, metadata = run_eco_lattice(rgb, prompt or {})
        artifacts = metadata.pop("_artifact_masks", {})
        prior_visible = artifacts.pop("router_prior_visible", None)
        if prior_visible is None:
            prior_stages, _prior_metadata = run_eco_lattice_v01(rgb, {})
            prior_visible = prior_stages["E6"]
        metadata.update({
            "case_id": _clean_case_id(case_id),
            "image_width": int(rgb.shape[1]),
            "image_height": int(rgb.shape[0]),
            "source_sha256": hashlib.sha256(_png_bytes(rgb)).hexdigest(),
            "duration_seconds": round(time.perf_counter() - started, 3),
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
        # Evaluation is deliberately a post-hoc diagnostic. It is executed after
        # every ECO stage is complete and cannot influence extraction.
        metadata["diagnostic_reference_comparison"] = _eco_diagnostic_reference_comparison(
            case_id,
            artifacts.get("visible", stages["E6"]),
            artifacts.get("completed", stages["E6"]),
            prior_visible,
        )
        output_dir = _save_eco_lattice_result(case_id, rgb, stages, metadata, artifacts)
        visible = artifacts.get("visible", stages["E6"])
        uncertain = artifacts.get("uncertain", np.zeros_like(visible, dtype=bool))
        bridge = artifacts.get("bridge", np.zeros_like(visible, dtype=bool))
        completed = artifacts.get("completed", visible | bridge)
        interference = artifacts.get("interference", np.zeros_like(visible, dtype=bool))
        occluder = artifacts.get("occluder", np.zeros_like(visible, dtype=bool))
        confidence = np.zeros(visible.shape, dtype=np.uint8)
        confidence[interference] = 45
        confidence[uncertain] = 135
        confidence[bridge] = 160
        confidence[visible] = 255
        return {
            "status": "complete",
            "method": method,
            "case_id": _clean_case_id(case_id),
            "stages": {
                name: {
                    "mask": _data_url(_mask_png(mask)),
                    "overlay": _data_url(_completion_overlay(rgb, visible, bridge)) if name == "E6" else None,
                    "metadata": metadata["stages"][name],
                }
                for name, mask in stages.items()
            },
            "artifacts": {
                "interference": _data_url(_mask_png(interference)),
                "occluder": _data_url(_mask_png(occluder)),
                "visible": _data_url(_mask_png(visible)),
                "completed": _data_url(_mask_png(completed)),
                "completedOverlay": _data_url(_completion_overlay(rgb, visible, bridge)),
                "obstacleOverlay": _data_url(_obstacle_diagnostic_overlay(rgb, visible, interference, occluder)),
                "uncertain": _data_url(_mask_png(uncertain)),
                "ccc": _data_url(_mask_png(artifacts.get("ccc", np.zeros_like(visible, dtype=bool)))),
                "continuity": _data_url(_mask_png(artifacts.get("continuity", np.zeros_like(visible, dtype=bool)))),
                "tgc": _data_url(_mask_png(artifacts.get("tgc", np.zeros_like(visible, dtype=bool)))),
                "sra": _data_url(_mask_png(artifacts.get("sra", np.zeros_like(visible, dtype=bool)))),
                "bridge": _data_url(_mask_png(bridge)),
                "confidence": _data_url(confidence),
                "skeleton": _data_url(_mask_png(artifacts.get("skeleton", _skeleton(visible) > 0))),
                "roi": _data_url(_mask_png(artifacts.get("roi", np.ones_like(visible, dtype=bool)))),
                "frame": _data_url(_mask_png(artifacts.get("frame", np.zeros_like(visible, dtype=bool)))),
                "frameObserved": _data_url(_mask_png(artifacts.get("frame_observed", np.zeros_like(visible, dtype=bool)))),
                "frameInferred": _data_url(_mask_png(artifacts.get("frame_inferred", np.zeros_like(visible, dtype=bool)))),
            },
            "metadata": metadata,
            "output_dir": str(output_dir),
        }
    if method == "c_sam":
        stages, metadata = run_c_sam(rgb, prompt or {})
        artifacts = metadata.pop("_artifact_masks", {})
        metadata.update({
            "case_id": _clean_case_id(case_id),
            "image_width": int(rgb.shape[1]),
            "image_height": int(rgb.shape[0]),
            "source_sha256": hashlib.sha256(_png_bytes(rgb)).hexdigest(),
            "duration_seconds": round(time.perf_counter() - started, 3),
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
        output_dir = _save_c_sam_result(case_id, rgb, stages, metadata, artifacts)
        return {
            "status": "complete",
            "method": method,
            "case_id": _clean_case_id(case_id),
            "stages": {
                name: {
                    "mask": _data_url(_mask_png(mask)),
                    "overlay": _data_url(_overlay(rgb, mask)) if name == "C6" else None,
                    "metadata": metadata["stages"][name],
                }
                for name, mask in stages.items()
            },
            "artifacts": {
                "obstacle": _data_url(_mask_png(artifacts.get("obstacle", np.zeros(stages["C6"].shape, dtype=bool)))),
                "observed": _data_url(_mask_png(artifacts.get("observed", stages["C4"]))),
                "inferred": _data_url(_mask_png(artifacts.get("inferred", stages["C5"] & ~stages["C4"]))),
                "confidence": _data_url(np.where(artifacts.get("observed", stages["C4"]), 255, np.where(artifacts.get("inferred", stages["C5"] & ~stages["C4"]), 145, np.where(stages["C6"], 205, 0))).astype(np.uint8)),
                "skeleton": _data_url(_mask_png(_skeleton(stages["C6"]) > 0)),
            },
            "metadata": metadata,
            "output_dir": str(output_dir),
        }
    if method == "sam_b":
        mask, metadata = run_sam_baseline(rgb, prompt or {})
    elif method == "c_rule":
        mask, metadata = run_c_rule(rgb)
    else:
        raise ValueError("method must be sam_b, c_rule, c_sam or eco_lattice")
    metadata.update({
        "case_id": _clean_case_id(case_id),
        "image_width": int(rgb.shape[1]),
        "image_height": int(rgb.shape[0]),
        "foreground_pixels": int(mask.sum()),
        "foreground_coverage": round(float(mask.mean()), 6),
        "source_sha256": hashlib.sha256(_png_bytes(rgb)).hexdigest(),
        "duration_seconds": round(time.perf_counter() - started, 3),
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    })
    output_dir = _save_result(method, case_id, rgb, mask, metadata)
    return {
        "status": "complete",
        "method": method,
        "case_id": _clean_case_id(case_id),
        "mask": _data_url(_mask_png(mask)),
        "overlay": _data_url(_overlay(rgb, mask)),
        "metadata": metadata,
        "output_dir": str(output_dir),
    }


def segmentation_runtime_status() -> dict[str, Any]:
    open_status = open_vocab_runtime_status()
    return {
        "sam_ready": open_status["ready"],
        "checkpoint": open_status["sam_model"],
        "checkpoint_size_mb": 0,
        "model_type": "Grounding DINO + SAM2.1 Hiera Small",
        "device": open_status["device"],
        "grounding_model": open_status["grounding_model"],
        "sam2_model": open_status["sam_model"],
        "models_loaded": open_status["loaded"],
        "training_required": False,
        "c_rule_ready": True,
        "c_sam_ready": open_status["ready"],
        "c_sam_version": "lattice_oatf_v2_zero_shot",
        "eco_lattice_ready": True,
        "eco_lattice_version": "eco_lattice_v0.8_occluder_illumination_router_prototype",
    }
