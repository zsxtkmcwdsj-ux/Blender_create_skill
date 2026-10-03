READ CONTRACT: blender-mcp-reference-modeling/references/workflow.md
EXTERIOR STRUCTURE GATE: build recognizable exterior structure before ornament: base/plinth, body/facade, column rhythm, openings, roof tiers, eaves, and ground contact.
STAIR AND BALUSTRADE GATE: every stair must have real treads, risers, landing slabs, side cheeks/stringers, guard posts, and a clear connection to each terrace level. Balustrades must break at stair openings and reconnect at platforms.
NO FILLER LANDSCAPE: do not add trees, people, vehicles, water, or decorative site filler unless the user explicitly asks for them.
MATERIAL REALISM GATE: separate stone, lacquered timber, glazed roof tile, metal/gold trim, and paving. Add roughness, bump/noise, edge bevels, seams, tile ribs, color variation, and weathering restrained by reference.
DELIVERY VIEWS: provide hero exterior, facade detail, roof/eave detail, and stair/terrace audit view.
使用 blender-mcp-reference-modeling 创建一个现实风格建筑外观场景。
模式：concept_spatial_modeling / exterior_architecture。重点是外观体量、结构连接、屋顶檐口、立面节奏、入口、台基楼梯、栏杆和材质细节。
EVIDENCE LEDGER: label each boundary, dimension, opening, and material as confirmed, inferred, or unknown. Do not turn weak sources into exact dimensions.
用户目标：Generate a photorealistic exterior architectural visualization of Tiananmen Gate that accurately conveys its iconic volumetric composition, hierarchical roof structure, material hierarchy (vermilion walls, yellow glazed tiles), and ornamental grammar (dougong, latticed windows, stone栏杆, ridge beasts), prioritizing spatial legibility and atmospheric authenticity over metric precision.
资料判断：建筑=high，楼层/区域=high，总体=exact_match。All key architectural identifiers match: 'Tiananmen Gate' is unambiguously named across multiple authoritative sources (China Daily, Wikipedia, Jianzhuzhichuang, 360Cities); structural identity (reconstructed 1651, post-1420 original) and formal typology (palace-style, not pavilion or gatehouse) are consistently confirmed; floor/level identity is explicitly stated as two-tiered (lower red brick city platform + upper timber-framed pavilion); visual features (red walls, multi-layered roof, dougong, latticed windows, balustrades, glazed tile roof, dragon-ornamented ridges) are repeatedly described and cross-verified.
必须表达的空间/构件：city platform、upper pavilion、roof ensemble、front facade
空间/结构关系：The city platform establishes grounded monumentality and axial symmetry; the upper pavilion expresses hierarchical authority through proportion (9 bays × 5 depths = 'Nine-Five' imperial symbolism); the roof ensemble articulates ritual hierarchy via ridge count, color (yellow = imperial), and beast sequence.
视觉方向：Chinese imperial architecture, Ming–Qing transitional style；材质：vermilion-painted brick and timber、yellow glazed ceramic roof tiles、Hanbaiyu (white marble) base and balustrade、gold-leafed lacquer paint on dougong and beams；灯光：clear daylight, frontal sun angle emphasizing relief of dougong, ridge ornaments, and window latticework；氛围：solemn, monumental, ceremonial, historically resonant
质量门槛：Roof ridge geometry must conform to 'eight eaves, nine ridges' structural logic；No interior room layout or furniture modeling — strictly exterior envelope and surface treatment；All materials must be physically plausible for Blender Cycles/Eevee rendering (PBR textures, normal maps, displacement where appropriate)；Balustrade height and spacing must support human-scale readability (approx. 1.2 m top rail, 0.35 m baluster spacing)
提示词配方：Use real-world reference proportions — avoid cartoonish exaggeration of bracket depth or roof pitch；Prioritize material fidelity over geometric perfection: slight irregularities in tile alignment and wood grain acceptable；Render all architectural elements as built assemblies — no floating geometry or disconnected parts；Exclude modern signage, scaffolding, or non-historical infrastructure
交付视角：Front elevation (full-frame, centered, eye-level at 1.6 m)；3/4 front-right perspective (showing roof slope, corner dougong, and balustrade continuity)；Detail close-up of dougong cluster under eave (with visible 'qiao', 'ang', 'gong' components)；Roof plan view (showing ridge layout and chiwen positions)
按阶段执行：资料冻结和坐标设定 → 主体 blockout → 空间/结构细化 → 材质 → 灯光和相机 → 验证和交付。
未知尺寸和局部细节允许合理发挥，但要把它们作为概念推断，不要伪装成真实测量值。
输出 .blend、.glb 和至少一张预览图；导出后重新检查 GLB。
工作目录：E:\app\condex_project\Blender_create_skill\runs\gugong_corner_visual
RESEARCH TO MODEL PROMPT PACKAGE:
- target lock: 生成一个现实风格的天安门城楼外观，重点体现红墙、多层屋顶、檐口、斗拱、栏杆、窗棂和屋顶瓦片细节等
- build order: freeze target identity and source confidence | block out recognizable massing before small decoration | add structural connections and circulation details | add signature facade, roof, opening and edge details | apply separated realistic materials with roughness, noise and bump | render hero and close-up audit views before export
- detail targets: overall silhouette and tier proportions; base or plinth connection to the ground; entrances, doors, windows and facade rhythm; stairs with real treads, risers, landings and rail openings; guardrails split into posts, panels, caps and breaks at entrances; roof massing, eaves, ribs, tile courses, underside structure and finial details; material separation for stone, timber, roof tile, metal trim and paving
- signature feature rules: compound_roof_and_tiles => roof cannot be a single flat slab; use separate roof mass, eave underside, raised ridges and repeated tile plates or tile ribs; model main ridge, vertical ridges and diagonal hip ridges when the reference implies compound or hip roofs; stacked roof tiers must have visible support bodies, columns or bracket layers between tiers; no upper roof may float above empty air; add finial, ridge caps, eave trim and upturned corner emphasis when visible | dougong_brackets => dougong cannot be isolated cubes; build stacked bracket blocks, cantilever arms and beam seats under the eave; use at least two colors or material layers for painted bracket blocks when reference supports painted timber | ornamental_lattice_windows => windows need recessed dark glass or interior shadow, outer frame thickness, vertical bars, horizontal bars and diagonal or ornamental bars when named; avoid one simple cross when the request mentions ornamental lattice or historical window patterns | stone_balustrade_and_stairs => stairs need individual treads, risers, side cheeks, landing slabs and clear railing openings; stone balustrades need separate posts, caps, panels, relief strips and breaks at stair entrances | plinth_wall_ground_connection => ground contact needs a believable base or plinth, not a floating building body; the main body, columns and plinth must physically touch or overlap through hidden support blocks; do not leave visible shadow gaps under the building; historic wall or terrace connections need visible courses, seams, edges and material separation
- material targets: stone; timber; roof_tile; metal; glass; fabric
- negative constraints: no unrelated filler objects unless requested; no white clay final material; no single-color plastic look; no floating slabs, fake painted openings or disconnected parts; no guardrail passing through stairs or entrances
- audit views: Front elevation (full-frame, centered, eye-level at 1.6 m); 3/4 front-right perspective (showing roof slope, corner dougong, and balustrade continuity); Detail close-up of dougong cluster under eave (with visible 'qiao', 'ang', 'gong' components); Roof plan view (showing ridge layout and chiwen positions)
- default production standard: focus on the requested building only; do not fill the scene with unrelated trees or decoration; lock the main silhouette, proportions and tier relationships before adding ornament; model real circulation parts: stairs need treads, risers, landings, side rails and clear railing openings; model guardrails as separate posts, panels, caps and directional breaks rather than continuous rings through entrances; add facade depth: columns, doors, lattice panels, plaques, brackets, eaves and visible joints; add roof depth: tiered masses, ribs, tile courses, eave trim, underside structure and finial details; use material variation: color, roughness, procedural noise and bump so the browser GLB is not a white clay model; render hero and close-up checks for overall shape, roof/eave detail, facade detail and stair/terrace detail; validate the exported GLB before publishing it to the model showcase
- evidence converted into prompt targets:
  * 详解天安门城楼的建筑特色 - China Daily :: 天安门城楼大殿为重檐歇山式屋顶，有正脊一条，正脊的两端有一对华丽的龙型琉璃装饰物，称为龙吻（又称大吻或正吻），另有垂脊8条，在垂脊顶端各有一条龙吻，故有“九脊封十龙”的说法。
...
天安门城楼为木结构建筑，大殿飞檐下令人眼花缭乱而又排列有序的斗拱和梁枋。斗拱为我国传统木构架体系中独有，是斗形木弓形横木组成的具有翘、昂、拱特点的木制构件。梁枋又分额枋、檐枋，斗拱下面是额枋，上面彩画和金龙图案，柱子之间的构件叫檐枋，会有金龙和玺图案。
...
天安门城楼大殿内有60根直径为92厘米的红漆木柱，承受着屋顶建筑大部分重力。正面的36扇门窗为中国传统的菱花格式，屋顶上的天花藻井画的是团龙图案，在殿厅堂纵横交错的梁枋上绘的是金龙和玺彩绘；17盏古雅的大型宫灯，最大的那盏称为主灯，有8个面，全高6米，直径2.8米，重约450公斤；其余16盏为6个面的辅灯，每个高6米，直径2.2米，重约350公斤。每盏灯上的角各有一盏伞形小灯。
  * 详解天安门城楼的建筑特色 :: 天安门城楼大殿为重檐歇山式屋顶，有正脊一条，正脊的两端有一对华丽的龙型琉璃装饰物，称为龙吻（又称大吻或正吻），另有垂脊8条，在垂脊顶端各有一条龙吻，故有“九脊封十龙”的说法。
...
天安门城楼为木结构建筑，大殿飞檐下令人眼花缭乱而又排列有序的斗拱和梁枋。斗拱为我国传统木构架体系中独有，是斗形木弓形横木组成的具有翘、昂、拱特点的木制构件。梁枋又分额枋、檐枋，斗拱下面是额枋，上面彩画和金龙图案，柱子之间的构件叫檐枋，会有金龙和玺图案。
...
屋顶巨型宫灯
...
天安门城楼大殿内有60根直径为92厘米的红漆木柱，承受着屋顶建筑大部分重力。正面的36扇门窗为中国传统的菱花格式，屋顶上的天花藻井画的是团龙图案，在殿厅堂纵横交错的梁枋上绘的是金龙和玺彩绘；17盏古雅的大型宫灯，最大的那盏称为主灯，有8个面，全高6米，直径2.8米，重约450公斤；其余16盏为6个面的辅灯，每个高6米，直径2.2米，重约350公斤。每盏灯上的角各有一盏伞形小灯。
  * 天安门 :: 天安门城楼内的天花板
...
天安门城楼内的大会客室
...
天安门城楼内的窗户
...
天安门城楼内的走廊，左侧进入楼内，右侧可以瞭望天安门广场
...
天安门城楼的楼梯
...
这里步行登上天安门城楼
...
天安门坐北朝南，原通高33.7米，1970年重修后改为34.7米。建筑的底部为汉白玉精雕的须弥座，高1.59米。底座上建有朱红色的高大城台，面积约440000平米。城台的两侧有登城马道，台上建城楼。
...
侧翼部分
  * 地标建筑 天安门 - 建筑之窗 :: 有汉白玉
...
天安门城楼为中国传统的重檐歇山顶建筑，即由四个倾斜的顶面、一条正脊、四条垂脊、四条戗脊（垂脊下端折向的一条）和两侧倾斜层面上部转折成垂直的三角形墙面组成，形成两坡和四坡屋顶的混合形式。故有“八檐九脊”之称。城楼为木结构建筑，大殿飞檐下是排列有序的斗拱和梁枋。斗拱为中国传统木构架体系中独有，是斗形木弓形横木组成的具有翘、昂、拱特点的木制构件。梁枋又分额枋、檐枋，斗拱下面是额枋，上面彩画和金龙图案，柱子之间的构件叫檐枋，会有金龙和玺图案。
...
城楼的主体建筑分为上下两层。上层是重檐歇山式，黄琉璃瓦顶的巍峨城楼，东西面阔九楹，南北进深五间，取“九五”之数，象征皇帝的尊严。正面有36扇菱花格式的门窗。城楼内所用木材大部分是楠木，大殿内有60根直径为92厘米的红漆木柱，承受着屋顶建筑大部分重力。排列整齐，柱顶上有藻井与梁枋，绘着金龙吉祥彩画和团龙图案。正面的36扇门窗为中国传统的菱花格式，屋顶上的天花藻井画的是团龙图案，在殿厅堂纵横交错的梁枋上绘的是金龙和玺彩绘；17盏古雅的大型宫灯，最大的那盏称为主灯，有8个面，全高6米，直径2.8米，重约450公斤；其余16盏为6个面的
  * 北京天安门2.5d正版高清图片下载-视觉中国VCG.COM :: 北京天安门2.5d正版高清图片下载-视觉中国VCG.COM
...
# 北京天安门2.5d
...
北京天安门2.5d图片素材作品是由视觉中国旗下网站（VCG.COM）的图片品牌合作方：Shijue Select提供，作品作者是:签约供稿人/视觉中国；图片ID:VCG211552396256；最大规格:AI 矢量图形；存储大小:2.91 MB - AI;授权方式是:；当前图片素材提供下载与正版授权服务，助力您的品牌提升。
...
最大尺寸：AI 矢量图形 | 79.81 x 44.83 cm (31.42 x 17.65 in.)
  * Tian An Men 天安门 (259) 360 Panorama | 360Cities :: 天安门：

 天安门的主体建筑分为上下两层。

 上层是重檐歇山式，黄琉璃瓦顶的巍峨城楼，东西面阔九楹，南北进深五间，取“九五”之数，象征着皇帝的尊严。正面有36扇菱花格式门窗。城楼基座周围有汉白玉栏杆、栏板，雕刻着莲花宝瓶图案。城楼内所用木材大部分是楠木，60根红漆巨柱排列整齐，柱顶上有藻井与梁枋，绘着金龙吉祥彩画和团龙图案。地面铺的全是金砖，面积约2000平方米。屋顶的正脊与垂脊上装饰着螭吻、仙人、走兽；17盏古雅的大型宫灯，最大的那盏称为主灯，有8个面，全高6米，直径2.8米，重约450公斤，其余的16盏为6个面的辅灯，每个高6米，直径2.2米，重约350公斤。每盏灯上的角各有一盏伞形小等。
...
下层是高13米的朱红色城台，四周环绕琉璃瓦封顶的矮墙，下部是1.59米高的雕刻精美的汉白玉须弥座台基。城台的总面积达4800平方米，东西两侧各有一条长达百级供上下城楼用的梯道，俗称马道。还有5个拱形门洞，中间的门洞最大，高8.82米，宽5.25米，唯有皇帝可以进出。

 城楼前有外金水河，河上飞架7座汉白玉雕栏石桥，中间一座最宽阔的称“御路桥”，专为皇帝而设。御路桥两旁有宗室亲王过往
- close-up failure checks:
  * roof close-up fails if the roof reads as one smooth board, lacks tile/ridge hierarchy, or any tier floats without support
  * facade close-up fails if bracket blocks do not visually support the eave
  * facade close-up fails if windows read as flat black rectangles with only one cross
  * stair close-up fails if stairs are a ramp, a single block, or if railings cross the stair opening
  * overview fails if the building body, columns, base, wall or terrace appear detached or hovering
硬约束：No interior spaces modeled — zero floor plans, ceilings, or room volumes beyond envelope shell；No human figures, vehicles, or landscape beyond immediate plinth and outer Golden River bridges；All dimensions must remain relative and scalable — no fixed metric units required；Do not model structural internals (nails, joinery, framing members) unless visually exposed and documented
不确定性：Exact tile size and laying pattern (source mentions 'glazed yellow tiles' but not module dimensions)；Precise dougong layer count per bracket set (described as 'layered' and 'ordered' but no count given)；Balustrade height above platform edge (only total platform height and base height provided)；Exact number and arrangement of zodiac beasts beyond '1 immortal + 9 beasts' — order may vary by source