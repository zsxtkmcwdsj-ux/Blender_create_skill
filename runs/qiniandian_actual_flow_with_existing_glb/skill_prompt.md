READ CONTRACT: blender-mcp-reference-modeling/references/workflow.md
EXTERIOR STRUCTURE GATE: build recognizable exterior structure before ornament: base/plinth, body/facade, column rhythm, openings, roof tiers, eaves, and ground contact.
STAIR AND BALUSTRADE GATE: every stair must have real treads, risers, landing slabs, side cheeks/stringers, guard posts, and a clear connection to each terrace level. Balustrades must break at stair openings and reconnect at platforms.
NO FILLER LANDSCAPE: do not add trees, people, vehicles, water, or decorative site filler unless the user explicitly asks for them.
MATERIAL REALISM GATE: separate stone, lacquered timber, glazed roof tile, metal/gold trim, and paving. Add roughness, bump/noise, edge bevels, seams, tile ribs, color variation, and weathering restrained by reference.
DELIVERY VIEWS: provide hero exterior, facade detail, roof/eave detail, and stair/terrace audit view.
使用 blender-mcp-reference-modeling 创建一个现实风格建筑外观场景。
模式：concept_spatial_modeling / exterior_architecture。重点是外观体量、结构连接、屋顶檐口、立面节奏、入口、台基楼梯、栏杆和材质细节。
EVIDENCE LEDGER: label each boundary, dimension, opening, and material as confirmed, inferred, or unknown. Do not turn weak sources into exact dimensions.
用户目标：生成祈年殿外观，重点楼梯和栏杆
资料判断：建筑=unknown，楼层/区域=unknown，总体=concept_reference。未完成模型判断，以下只作为概念设计输入。
必须表达的空间/构件：overall exterior massing、roof and eave system、facade rhythm and openings、terrace, stairs, and balustrades
空间/结构关系：base supports facade/body；stairs connect every visible terrace level；roof tiers align to facade/column rhythm
视觉方向：realistic exterior architectural reconstruction with source-led proportions；材质：stone、lacquered wood、glazed roof tile、metal/gold trim；灯光：daylight architectural presentation；氛围：realistic, detailed, restrained
质量门槛：recognizable massing before ornament: base/plinth, body, roof tiers, eaves, column grid, openings；stairs require real treads, risers, landings, side cheeks, rail openings, and verified connections to each terrace level；balustrades must break at stairs and reconnect to platforms; never let rails pass through a stair flight；do not add unrelated trees, people, vehicles, water, or filler landscaping unless requested；materials must separate stone, lacquered timber, glazed roof tiles, metal/gold trim, with visible roughness/bump variation
提示词配方：write the Blender task as a staged exterior recipe: reference lock, massing blockout, structural connections, signature details, materials, cameras, export audit；name must-have exterior components explicitly instead of asking for a generic realistic building；describe near-view detail targets: eaves, roof ribs/tiles, column bases/caps, plaque/door panels, terrace stairs, balustrade joints；state negative constraints in the prompt: no unrelated landscape filler, no floating plates, no rails crossing stair openings, no single-color plastic materials；ask for at least one close-up audit render of the weakest structural area
交付视角：hero exterior；front facade detail；roof/eave detail；stair and terrace connection audit
按阶段执行：资料冻结和坐标设定 → 主体 blockout → 空间/结构细化 → 材质 → 灯光和相机 → 验证和交付。
未知尺寸和局部细节允许合理发挥，但要把它们作为概念推断，不要伪装成真实测量值。
输出 .blend、.glb 和至少一张预览图；导出后重新检查 GLB。
工作目录：E:\app\condex_project\Blender_create_skill\runs\qiniandian_actual_flow_with_existing_glb
不确定性：未确认的具体尺寸、门洞和房间数量不得当成事实