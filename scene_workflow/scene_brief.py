from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from scene_workflow.research_to_prompt import prompt_package_lines


def parse_json(text: str) -> dict[str, Any]:
    value = (text or "").strip()
    value = re.sub(r"^```(?:json)?", "", value, flags=re.I).strip()
    value = re.sub(r"```$", "", value).strip()
    start, end = value.find("{"), value.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in model response")
    result = json.loads(value[start : end + 1])
    if not isinstance(result, dict):
        raise ValueError("scene brief must be an object")
    return result


def hard_finish_defaults() -> dict[str, Any]:
    return {
        "required": [
            "floor_finish",
            "wall_finish",
            "ceiling_finish",
            "skirting_or_baseboard",
            "door_window_frame_finish",
            "threshold_or_sill",
            "readable_room_light",
        ],
        "conditional": [
            "corner_guard_or_reveal",
            "switches_and_sockets",
            "hvac_grille",
            "detector_or_sprinkler",
            "waterproofing_and_floor_drain",
            "acoustic_or_curtain_finish",
        ],
        "exclude_by_default": ["furniture", "decorative_props", "unverified_equipment"],
    }


def normalize_generation_module(value: str | None) -> str:
    if value in {"exterior", "exterior_architecture", "outdoor", "室外", "外观"}:
        return "exterior_architecture"
    return "interior_space"


def quality_gates_for(module: str) -> list[str]:
    if module == "exterior_architecture":
        return [
            "recognizable massing before ornament: base/plinth, body, roof tiers, eaves, column grid, openings",
            "stairs require real treads, risers, landings, side cheeks, rail openings, and verified connections to each terrace level",
            "balustrades must break at stairs and reconnect to platforms; never let rails pass through a stair flight",
            "do not add unrelated trees, people, vehicles, water, or filler landscaping unless requested",
            "materials must separate stone, lacquered timber, glazed roof tiles, metal/gold trim, with visible roughness/bump variation",
        ]
    return [
        "closed rooms require continuous floor, wall, ceiling, and explicit openings before furniture",
        "doors and windows must be real holes with frames, thresholds or sills",
        "hard finishes are required before decorative props",
    ]


def delivery_views_for(module: str) -> list[str]:
    if module == "exterior_architecture":
        return ["hero exterior", "front facade detail", "roof/eave detail", "stair and terrace connection audit"]
    return ["hero interior", "cutaway or overview proving envelope/openings/adjacency"]


def prompt_directives_for(module: str) -> list[str]:
    if module == "exterior_architecture":
        return [
            "write the Blender task as a staged exterior execution plan: reference lock, massing blockout, structural connections, signature details, materials, cameras, export audit",
            "name must-have exterior components explicitly instead of asking for a generic realistic building",
            "describe near-view detail targets: eaves, roof ribs/tiles, column bases/caps, plaque/door panels, terrace stairs, balustrade joints",
            "state negative constraints in the prompt: no unrelated landscape filler, no floating plates, no rails crossing stair openings, no single-color plastic materials",
            "ask for at least one close-up audit render of the weakest structural area",
        ]
    return [
        "write the Blender task as a staged interior execution plan: envelope, openings, hard finishes, circulation, furniture/equipment only after structure",
        "name room boundaries, door/window holes, thresholds/sills, skirting, ceiling, lighting, and adjacency before style words",
        "state negative constraints in the prompt: no floating walls, no fake doors painted on walls, no decorative props before hard finishes",
        "ask for one section/cutaway render that proves the room enclosure",
    ]


def fallback_brief(question: str, sources: list[dict[str, Any]], generation_module: str | None = None) -> dict[str, Any]:
    module = normalize_generation_module(generation_module)
    room_space: tuple[str, str] | None = None
    if any(term in question for term in ("room", "bedroom", "dorm", "meeting room", "classroom", "studio", "bathroom", "宿舍", "房间", "会议室", "教室", "工作室", "卫生间")):
        room_space = ("single enclosed room", "room")
    if any(term in question for term in ("\u5bbf\u820d", "\u623f\u95f4", "\u4f1a\u8bae\u5ba4", "\u6559\u5ba4", "\u5de5\u4f5c\u5ba4", "\u536b\u751f\u95f4")):
        room_space = ("single enclosed room", "room")
    if "\u4f1a\u8bae\u5ba4" in question:
        room_space = ("meeting room", "room")
    elif "\u5bbf\u820d" in question:
        room_space = ("student dormitory room", "room")
    if any(term in question for term in ("会议室", "meeting room")):
        room_space = ("meeting room", "room")
    elif any(term in question for term in ("宿舍", "dormitory", "dorm")):
        room_space = ("student dormitory room", "room")
    keywords = [
        (("入口", "门厅", "大厅"), "入口", "lobby"),
        (("吧台", "服务台", "前台", "柜台"), "吧台/服务区", "service_space"),
        (("座位", "用餐", "阅读", "展览", "公共"), "主要公共区", "common_area"),
        (("后厨", "厨房", "备餐"), "后厨/备餐区", "service_space"),
        (("走廊", "动线"), "主走廊", "corridor"),
        (("楼梯", "疏散"), "楼梯间", "stairwell"),
        (("电梯",), "电梯厅", "elevator"),
    ]
    spaces: list[dict[str, str]] = []
    for terms, name, kind in keywords:
        if any(term in question for term in terms) and not any(item["type"] == kind and item["name"] == name for item in spaces):
            spaces.append({"name": name, "type": kind})
    if room_space:
        spaces = [{"name": room_space[0], "type": room_space[1]}]
    if module == "exterior_architecture":
        spaces = [
            {"name": "overall exterior massing", "type": "exterior"},
            {"name": "roof and eave system", "type": "roof"},
            {"name": "facade rhythm and openings", "type": "facade"},
            {"name": "terrace, stairs, and balustrades", "type": "terrace"},
        ]
    elif not spaces:
        spaces = [{"name": "入口/公共大厅", "type": "lobby"}, {"name": "主要公共功能区", "type": "common_area"}]
    if module != "exterior_architecture" and not room_space and not any(item["type"] == "corridor" for item in spaces):
        spaces.insert(1, {"name": "主交通空间", "type": "corridor"})
    envelope_mode = "open" if module == "exterior_architecture" else "closed" if room_space else "semi_open"
    envelope_model = "assembled_elements_with_verified_joints" if module == "exterior_architecture" else "continuous_shell_with_explicit_openings"
    return {
        "mode": "concept_spatial_modeling",
        "generation_module": module,
        "envelope_model": envelope_model,
        "spatial_envelope": {"mode": envelope_mode, "footprint": "inferred room footprint" if room_space else "inferred architectural/site footprint", "boundary_segments": ["floor", "four continuous walls", "ceiling"] if room_space else ["site plane", "plinth/base", "facade/body", "ceiling_or_roof"], "openings": ["door", "window"] if room_space else ["door", "window", "stair_access", "terrace_edge"], "vertical_connections": []},
        "target_verification": {"building_identity": "unknown", "floor_identity": "unknown", "visual_relevance": "unknown", "verdict": "concept_reference", "reason": "未完成模型判断，以下只作为概念设计输入。"},
        "scene_goal": question,
        "spaces": spaces,
        "space_contracts": [{"space": item["name"], "boundary_mode": "closed", "floor": True, "walls": ["side boundaries", "ceiling boundary"], "ceiling": True, "openings": ["door to circulation"], "connections": [], "vertical_geometry": [], "content_after_envelope": []} for item in spaces],
        "hard_finish": hard_finish_defaults(),
        "adjacency_graph": [],
        "relationships": ["base supports facade/body", "stairs connect every visible terrace level", "roof tiers align to facade/column rhythm"] if module == "exterior_architecture" else ["主交通空间连接入口和主要公共功能区", "服务或垂直交通空间靠近公共动线"],
        "visual_language": {"style": "realistic exterior architectural reconstruction with source-led proportions", "materials": ["stone", "lacquered wood", "glazed roof tile", "metal/gold trim"], "lighting": "daylight architectural presentation", "mood": "realistic, detailed, restrained"} if module == "exterior_architecture" else {"style": "根据目标建筑类型做简洁的概念化表达", "materials": ["stone", "wood", "glass", "metal"], "lighting": "柔和的建筑展示光", "mood": "清晰、开敞、可读"},
        "must_have": [item["name"] for item in spaces],
        "quality_gates": quality_gates_for(module),
        "delivery_views": delivery_views_for(module),
        "prompt_directives": prompt_directives_for(module),
        "soft_constraints": ["不要求一比一复刻", "局部尺寸和装饰允许合理发挥"],
        "uncertainties": ["未确认的具体尺寸、门洞和房间数量不得当成事实"],
        "sources": [{"title": item.get("title", ""), "url": item.get("url", ""), "channel": item.get("channel", "")} for item in sources[:12]],
    }


def synthesis_prompt(question: str, research: dict[str, Any], generation_module: str | None = None) -> str:
    module = normalize_generation_module(generation_module)
    compact = []
    for item in research.get("sources", [])[:24]:
        compact.append({"channel": item.get("channel"), "title": item.get("title"), "url": item.get("url"), "snippet": item.get("snippet", "")[:600]})
    return f"""
你是建筑概念场景总监。用户想把自然语言需求交给 Blender 建成一个空间概念正确、视觉完整的建筑场景。

用户需求：{question}
生成模块：{module}

请先判断联网资料是否真的对应用户目标：建筑身份、楼层/区域身份、图片相关性必须分开判断。不能因为名称相似就替换用户目标。资料不足时输出 concept_reference，不要编造精确尺寸。

本任务不追求真实建筑一比一复刻，只追求：主要空间、排布、动线、功能关系和建筑氛围正确。请把事实、合理推断和未知分开。
如果生成模块是 exterior_architecture，重点输出外观体量、屋顶/檐口、立面节奏、台基、楼梯、栏杆、入口和外立面材质；不要输出室内房间合同。不要根据关键词自行切换模块。
如果生成模块是 interior_space，重点输出连续空间围合、门窗洞口、硬装、动线和相邻关系。

资料：
{json.dumps(compact, ensure_ascii=False, indent=2)}

只输出 JSON：
{{
  "target_verification": {{"building_identity":"high|medium|low|unknown", "floor_identity":"high|medium|low|unknown", "visual_relevance":"high|medium|low|unknown", "verdict":"exact_match|building_match_only|context_match|concept_reference|unrelated", "reason":""}},
  "generation_module":"interior_space|exterior_architecture",
  "scene_goal":"",
  "spaces":[{{"name":"", "type":"lobby|corridor|room|common_area|service_space|bathroom|stairwell|elevator|exterior|roof|facade|terrace", "confidence":"confirmed|inferred"}}],
  "space_contracts":[{{"space":"", "boundary_mode":"closed|semi_open|open", "floor":true, "walls":[""], "ceiling":true, "openings":[""], "connections":[""], "vertical_geometry":[""], "content_after_envelope":[""]}}],
  "envelope_model":"continuous_shell_with_explicit_openings|assembled_elements_with_verified_joints",
  "hard_finish":{{"required":["floor_finish","wall_finish","ceiling_finish","skirting_or_baseboard","door_window_frame_finish","threshold_or_sill","readable_room_light"], "conditional":["switches_and_sockets","hvac_grille","detector_or_sprinkler","waterproofing_and_floor_drain","acoustic_or_curtain_finish"], "exclude_by_default":["furniture","decorative_props","unverified_equipment"]}},
  "adjacency_graph":[{{"from":"", "to":"", "connection":"door|corridor|stair|elevator|open_edge", "confidence":"confirmed|inferred"}}],
  "relationships":[""],
  "spatial_envelope":{{"mode":"closed|semi_open|open", "footprint":"", "boundary_segments":["floor", "wall", "ceiling|roof"], "openings":["door", "window", "archway", "stair_void", "glass_edge"], "vertical_connections":[""]}},
  "visual_language":{{"style":"", "materials":[""], "lighting":"", "mood":""}},
  "must_have":[""],
  "quality_gates":[""],
  "delivery_views":[""],
  "prompt_directives":[""],
  "hard_constraints":[""],
  "soft_constraints":[""],
  "uncertainties":[""],
  "sources":[{{"title":"", "url":"", "channel":"", "reason":""}}]
}}
""".strip()


def blender_skill_prompt(brief: dict[str, Any], output_dir: Path, references: list[str]) -> str:
    target = brief.get("target_verification", {})
    visual = brief.get("visual_language", {})
    module = normalize_generation_module(brief.get("generation_module"))
    hard_finish = brief.get("hard_finish", hard_finish_defaults())
    quality_gates = brief.get("quality_gates") or quality_gates_for(module)
    delivery_views = brief.get("delivery_views") or delivery_views_for(module)
    prompt_directives = brief.get("prompt_directives") or prompt_directives_for(module)
    prompt_quality_package = brief.get("prompt_quality_package")
    common = [
        "EVIDENCE LEDGER: label each boundary, dimension, opening, and material as confirmed, inferred, or unknown. Do not turn weak sources into exact dimensions.",
        f"用户目标：{brief.get('scene_goal', '')}",
        f"资料判断：建筑={target.get('building_identity', 'unknown')}，楼层/区域={target.get('floor_identity', 'unknown')}，总体={target.get('verdict', 'concept_reference')}。{target.get('reason', '')}",
        "必须表达的空间/构件：" + "、".join(str(item.get("name", "")) for item in brief.get("spaces", [])),
        "空间/结构关系：" + "；".join(str(item) for item in brief.get("relationships", [])),
        f"视觉方向：{visual.get('style', '')}；材质：{'、'.join(str(item) for item in visual.get('materials', []))}；灯光：{visual.get('lighting', '')}；氛围：{visual.get('mood', '')}",
        "质量门槛：" + "；".join(str(item) for item in quality_gates),
        "提示词配方：" + "；".join(str(item) for item in prompt_directives),
        "交付视角：" + "；".join(str(item) for item in delivery_views),
        "按阶段执行：资料冻结和坐标设定 → 主体 blockout → 空间/结构细化 → 材质 → 灯光和相机 → 验证和交付。",
        "未知尺寸和局部细节允许合理发挥，但要把它们作为概念推断，不要伪装成真实测量值。",
        "输出 .blend、.glb 和至少一张预览图；导出后重新检查 GLB。",
        f"工作目录：{output_dir}",
    ]
    if prompt_quality_package:
        common.extend(prompt_package_lines(prompt_quality_package))
    if module == "exterior_architecture":
        lines = [
            "READ CONTRACT: blender-mcp-reference-modeling/references/workflow.md",
            "EXTERIOR STRUCTURE GATE: build recognizable exterior structure before ornament: base/plinth, body/facade, column rhythm, openings, roof tiers, eaves, and ground contact.",
            "STAIR AND BALUSTRADE GATE: every stair must have real treads, risers, landing slabs, side cheeks/stringers, guard posts, and a clear connection to each terrace level. Balustrades must break at stair openings and reconnect at platforms.",
            "NO FILLER LANDSCAPE: do not add trees, people, vehicles, water, or decorative site filler unless the user explicitly asks for them.",
            "MATERIAL REALISM GATE: separate stone, lacquered timber, glazed roof tile, metal/gold trim, and paving. Add roughness, bump/noise, edge bevels, seams, tile ribs, color variation, and weathering restrained by reference.",
            "DELIVERY VIEWS: provide hero exterior, facade detail, roof/eave detail, and stair/terrace audit view.",
            "使用 blender-mcp-reference-modeling 创建一个现实风格建筑外观场景。",
            "模式：concept_spatial_modeling / exterior_architecture。重点是外观体量、结构连接、屋顶檐口、立面节奏、入口、台基楼梯、栏杆和材质细节。",
            *common,
        ]
    else:
        lines = [
            "READ CONTRACT: blender-mcp-reference-modeling/references/closed-space-hard-finish.md",
            "SPATIAL ENVELOPE GATE: model the space as a complete volumetric container before furniture. Every space needs a floor, wall/glazing boundary, ceiling/roof, and explicit openings or connections. Classify each zone as closed, semi-open, or open.",
            "CLOSED-SPACE GATE: for a closed room, create one continuous shell or one semantically unified wall mesh with verified joints. Do not let separate wall pieces, slabs, or finish panels leave visible or physical gaps at corners, wall-floor, or wall-ceiling joints.",
            f"HARD FINISH SCOPE: required={', '.join(str(item) for item in hard_finish.get('required', []))}; conditional={', '.join(str(item) for item in hard_finish.get('conditional', []))}; exclude_by_default={', '.join(str(item) for item in hard_finish.get('exclude_by_default', []))}",
            "OPENING RULE: doors, windows, arches, stair voids, atriums, and curtain walls must be modeled as real boundary conditions with thickness, sill/head height, and a connection to an adjacent space. Do not use floating wall fragments or floating furniture to imply a room.",
            "OPENING OCCLUSION CHECK: test every door and window from both sides and in a section view. The parent wall must be absent inside the opening; the opening must retain wall beside it and above its head, then receive a frame, threshold/sill, leaf or glazing.",
            "HARD-FINISH GATE: before furniture, add floor finish, wall finish, ceiling finish, skirting/baseboard, door/window frame finish, threshold/sill, and at least one visible or defensible room light.",
            "DELIVERY VIEWS: provide a hero interior view plus one cutaway/section or overview view that proves the room envelope, openings, and adjacency graph.",
            "SPACE CONTRACT GATE: before furniture, verify every room has floor, side boundaries, ceiling, and framed openings; verify every corridor connects to rooms; verify every stair has landings and a continuous flight; verify every elevator has shaft, landing, doors, and vertical continuation.",
            "使用 blender-mcp-reference-modeling 创建一个概念性室内建筑场景。",
            "模式：concept_spatial_modeling / interior_space。重点是空间概念、布局、动线、连续围合和视觉表达。",
            *common,
        ]
    if brief.get("hard_constraints"):
        lines.append("硬约束：" + "；".join(str(item) for item in brief["hard_constraints"]))
    if brief.get("uncertainties"):
        lines.append("不确定性：" + "；".join(str(item) for item in brief["uncertainties"]))
    if references:
        lines.append("可查看的参考资料：\n" + "\n".join(f"- {item}" for item in references[:20]))
    return "\n".join(lines)
