from __future__ import annotations

import threading
import time
from typing import Any

import cv2
import numpy as np
from PIL import Image


GROUNDING_MODEL_ID = "IDEA-Research/grounding-dino-tiny"
SAM2_MODEL_ID = "facebook/sam2.1-hiera-small"
LATTICE_PROMPTS = (
    "traditional Chinese lattice window",
    "decorative window grille",
    "wooden lattice frame",
    "Chinese garden window",
)
OBSTACLE_PROMPTS = (
    "plant leaves",
    "tree branch",
    "rock",
    "stone",
    "wall texture",
)

_model_lock = threading.RLock()
_ground_processor: Any = None
_ground_model: Any = None
_sam_processor: Any = None
_sam_model: Any = None
_sam_device = "not_loaded"


def _load_models() -> tuple[Any, Any, Any, Any, str]:
    global _ground_processor, _ground_model, _sam_processor, _sam_model, _sam_device
    with _model_lock:
        if _ground_model is not None and _sam_model is not None:
            return _ground_processor, _ground_model, _sam_processor, _sam_model, _sam_device
        import torch
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor, Sam2Model

        _ground_processor = AutoProcessor.from_pretrained(GROUNDING_MODEL_ID)
        _ground_model = AutoModelForZeroShotObjectDetection.from_pretrained(GROUNDING_MODEL_ID)
        _ground_model.to("cpu").eval()
        _sam_processor = AutoProcessor.from_pretrained(SAM2_MODEL_ID)
        _sam_device = "mps" if torch.backends.mps.is_available() else "cpu"
        _sam_model = Sam2Model.from_pretrained(SAM2_MODEL_ID)
        _sam_model.to(_sam_device).eval()
        return _ground_processor, _ground_model, _sam_processor, _sam_model, _sam_device


def _is_obstacle(label: str) -> bool:
    lower = label.lower()
    return any(token in lower for token in ("plant", "leaf", "leaves", "branch", "rock", "stone", "wall"))


def _box_area(box: list[float], width: int, height: int) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1]) / max(1.0, width * height)


def _clip_box(box: list[float], width: int, height: int, pad: float = 0.0) -> list[float]:
    x0, y0, x1, y1 = box
    px = (x1 - x0) * pad
    py = (y1 - y0) * pad
    return [
        float(max(0, min(width - 2, x0 - px))),
        float(max(0, min(height - 2, y0 - py))),
        float(max(1, min(width - 1, x1 + px))),
        float(max(1, min(height - 1, y1 + py))),
    ]


def _select_lattice_detection(detections: list[dict[str, Any]], width: int, height: int) -> tuple[dict[str, Any], str]:
    candidates = [item for item in detections if not _is_obstacle(item["label"])]
    plausible = [item for item in candidates if 0.045 <= item["area_ratio"] <= 0.985]
    if plausible:
        # A lattice photograph may contain a high-confidence emblem or central
        # motif. When the detector also proposes a credible large window/frame,
        # prefer that architectural extent so the baseline does not get an
        # artificially tiny crop.
        large = [item for item in plausible if item["area_ratio"] >= 0.45 and item["score"] >= 0.12]
        if large:
            return max(
                large,
                key=lambda item: item["score"] + 0.28 * min(item["area_ratio"], 0.92) - 0.8 * max(0.0, item["area_ratio"] - 0.975),
            ), "open_vocabulary_large_window_extent"
        def score(item: dict[str, Any]) -> float:
            area = item["area_ratio"]
            area_bonus = 0.20 * min(area, 0.82)
            whole_image_penalty = 0.65 * max(0.0, area - 0.92)
            return item["score"] + area_bonus - whole_image_penalty
        return max(plausible, key=score), "open_vocabulary_detection"
    return {
        "label": "automatic fallback window region",
        "score": 0.0,
        "box": [0.02 * width, 0.02 * height, 0.98 * width, 0.98 * height],
        "area_ratio": 0.9216,
    }, "detector_fallback"


def _segment_boxes(
    pil_image: Image.Image,
    boxes: list[list[float]],
    sam_processor: Any,
    sam_model: Any,
    device: str,
) -> tuple[list[np.ndarray], list[dict[str, Any]]]:
    if not boxes:
        return [], []
    import torch

    inputs = sam_processor(images=pil_image, input_boxes=[boxes], return_tensors="pt").to(device)
    with torch.inference_mode():
        outputs = sam_model(**inputs, multimask_output=True)
    masks = sam_processor.post_process_masks(outputs.pred_masks.cpu(), inputs["original_sizes"])[0]
    scores = outputs.iou_scores.detach().cpu().numpy()[0]
    selected_masks: list[np.ndarray] = []
    records: list[dict[str, Any]] = []
    for index in range(len(boxes)):
        box_masks = masks[index].numpy().astype(bool)
        box_scores = np.asarray(scores[index]).reshape(-1)
        coverages = np.asarray([float(mask.mean()) for mask in box_masks])
        # Generic candidate choice: trust SAM2 confidence, but reject the common
        # degenerate whole-image/background candidate. No lattice-specific repair
        # is performed here, so this remains a fair open-vocabulary baseline.
        quality = box_scores.copy()
        quality -= np.maximum(0.0, coverages - 0.78) * 1.35
        quality -= np.maximum(0.0, 0.006 - coverages) * 8.0
        selected = int(np.argmax(quality))
        selected_masks.append(box_masks[selected])
        records.append({
            "candidate_scores": [round(float(value), 6) for value in box_scores],
            "candidate_coverages": [round(float(value), 6) for value in coverages],
            "candidate_quality": [round(float(value), 6) for value in quality],
            "selected_candidate": selected,
            "predicted_iou": round(float(box_scores[selected]), 6),
        })
    return selected_masks, records


def run_open_vocabulary_sam2(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Zero-shot Grounding DINO + SAM2.1 baseline and independent obstacle proposals."""
    import torch

    started = time.perf_counter()
    ground_processor, ground_model, sam_processor, sam_model, device = _load_models()
    pil_image = Image.fromarray(rgb)
    height, width = rgb.shape[:2]
    prompt_text = ". ".join((*LATTICE_PROMPTS, *OBSTACLE_PROMPTS)) + "."
    with _model_lock:
        ground_inputs = ground_processor(images=pil_image, text=prompt_text, return_tensors="pt")
        with torch.inference_mode():
            ground_outputs = ground_model(**ground_inputs)
        processed = ground_processor.post_process_grounded_object_detection(
            ground_outputs,
            ground_inputs.input_ids,
            threshold=0.12,
            text_threshold=0.12,
            target_sizes=[(height, width)],
        )[0]

        detections: list[dict[str, Any]] = []
        for score, box, label in zip(processed["scores"], processed["boxes"], processed["labels"]):
            box_list = _clip_box([float(value) for value in box.tolist()], width, height)
            detections.append({
                "label": str(label),
                "score": round(float(score), 6),
                "box": [round(value, 3) for value in box_list],
                "area_ratio": round(_box_area(box_list, width, height), 6),
            })
        selected, selection_source = _select_lattice_detection(detections, width, height)
        selected_box = _clip_box(list(selected["box"]), width, height, pad=0.012)
        masks, sam_records = _segment_boxes(pil_image, [selected_box], sam_processor, sam_model, device)
        lattice_mask = masks[0] if masks else np.zeros((height, width), dtype=bool)

        obstacle_detections = [
            item for item in detections
            if _is_obstacle(item["label"]) and item["score"] >= 0.14 and item["area_ratio"] <= 0.72
        ]
        obstacle_detections = sorted(obstacle_detections, key=lambda item: item["score"], reverse=True)[:6]
        obstacle_boxes = [list(item["box"]) for item in obstacle_detections]
        obstacle_masks, obstacle_records = _segment_boxes(
            pil_image, obstacle_boxes, sam_processor, sam_model, device
        ) if obstacle_boxes else ([], [])

    obstacle_mask = np.zeros((height, width), dtype=bool)
    obstacle_details: list[dict[str, Any]] = []
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    green_support = (hsv[:, :, 0] >= 25) & (hsv[:, :, 0] <= 100) & (hsv[:, :, 1] >= 35)
    for detection, mask, record in zip(obstacle_detections, obstacle_masks, obstacle_records):
        label = detection["label"].lower()
        accepted = mask
        if any(token in label for token in ("plant", "leaf", "leaves", "branch")):
            accepted = mask & (cv2.dilate(green_support.astype(np.uint8), np.ones((7, 7), np.uint8), iterations=1) > 0)
        obstacle_mask |= accepted
        obstacle_details.append({**detection, **record, "accepted_pixels": int(accepted.sum())})

    metadata = {
        "method": "open_vocabulary_sam2_baseline",
        "algorithm_version": "grounded_sam2_zero_shot_v1",
        "definition": "Grounding DINO open-vocabulary localization followed by raw SAM2.1 segmentation; no manual points, brush, obstacle removal or topology repair",
        "training_or_finetuning": False,
        "manual_prompt": False,
        "grounding_model": GROUNDING_MODEL_ID,
        "sam_model": SAM2_MODEL_ID,
        "sam_device": device,
        "text_prompts": list(LATTICE_PROMPTS),
        "obstacle_prompts": list(OBSTACLE_PROMPTS),
        "detections": detections,
        "selected_detection": {**selected, "box": [round(value, 3) for value in selected_box]},
        "selection_source": selection_source,
        "sam2": sam_records[0] if sam_records else {},
        "obstacle_proposals": obstacle_details,
        "duration_seconds_model": round(time.perf_counter() - started, 3),
    }
    return lattice_mask.astype(bool), obstacle_mask.astype(bool), metadata


def runtime_status() -> dict[str, Any]:
    return {
        "ready": True,
        "grounding_model": GROUNDING_MODEL_ID,
        "sam_model": SAM2_MODEL_ID,
        "device": _sam_device,
        "loaded": _ground_model is not None and _sam_model is not None,
        "training_required": False,
    }
