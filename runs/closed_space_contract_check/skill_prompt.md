READ CONTRACT: blender-mcp-reference-modeling/references/closed-space-hard-finish.md
SPATIAL ENVELOPE GATE: model the space as a complete volumetric container before furniture. Every space needs a floor, wall/glazing boundary, ceiling/roof, and explicit openings or connections. Classify each zone as closed, semi-open, or open.
CLOSED-SPACE GATE: for a closed room, create one continuous shell or one semantically unified wall mesh with verified joints. Do not let separate wall pieces, slabs, or finish panels leave visible or physical gaps at corners, wall-floor, or wall-ceiling joints.
HARD FINISH SCOPE: required=floor_finish, wall_finish, ceiling_finish, skirting_or_baseboard, door_window_frame_finish, threshold_or_sill, readable_room_light; conditional=corner_guard_or_reveal, switches_and_sockets, hvac_grille, detector_or_sprinkler, waterproofing_and_floor_drain, acoustic_or_curtain_finish; exclude_by_default=furniture, decorative_props, unverified_equipment
OPENING RULE: doors, windows, arches, stair voids, atriums, and curtain walls must be modeled as real boundary conditions with thickness, sill/head height, and a connection to an adjacent space. Do not use floating wall fragments or floating furniture to imply a room.
OPENING OCCLUSION CHECK: test every door and window from both sides and in a section view. The parent wall must be absent inside the opening; the opening must retain wall beside it and above its head, then receive a frame, threshold/sill, leaf or glazing.
HARD-FINISH GATE: before furniture, add floor finish, wall finish, ceiling finish, skirting/baseboard, door/window frame finish, threshold/sill, and at least one visible or defensible room light. Add HVAC, sockets, detectors, sprinklers, waterproofing, drains, acoustic panels, or curtain tracks only when supported by the brief.
DELIVERY VIEWS: provide a hero interior view plus one cutaway/section or overview view that proves the room envelope, openings, and adjacency graph.
SPACE CONTRACT GATE: before furniture, verify every room has floor, side boundaries, ceiling, and framed openings; verify every corridor connects to rooms; verify every stair has landings and a continuous flight; verify every elevator has shaft, landing, doors, and vertical continuation.
EVIDENCE LEDGER: label each boundary, dimension, opening, and material as confirmed, inferred, or unknown. Never turn a campus-level source into exact Building 7 evidence.
使用 blender-mcp-reference-modeling 创建一个概念性室内建筑场景。
模式：concept_spatial_modeling。不要把它当成精确建筑复原；重点是空间概念、布局、动线和视觉表达。
用户目标：single enclosed student dorm room with real walls, door opening, window opening, and basic hard finish
资料判断：建筑=unknown，楼层/区域=unknown，总体=concept_reference。未完成模型判断，以下只作为概念设计输入。
必须表达的空间：入口/公共大厅、主交通空间、主要公共功能区
空间关系：主交通空间连接入口和主要公共功能区；服务或垂直交通空间靠近公共动线
视觉方向：根据目标建筑类型做简洁的概念化表达；材质：stone、wood、glass、metal；灯光：柔和的建筑展示光；氛围：清晰、开敞、可读
按阶段执行：资料冻结和坐标设定 → 主体 blockout → 空间/结构细化 → 材质 → 灯光和相机 → 验证和交付。
未知尺寸和局部细节允许合理发挥，但要把它们作为概念推断，不要伪装成真实测量值。
输出 .blend、.glb 和至少一张预览图；导出后重新检查 GLB。
工作目录：E:\app\condex_project\Blender_create_skill\runs\closed_space_contract_check
不确定性：未确认的具体尺寸、门洞和房间数量不得当成事实