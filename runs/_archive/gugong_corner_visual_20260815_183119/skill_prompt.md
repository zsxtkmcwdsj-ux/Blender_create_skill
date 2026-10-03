READ CONTRACT: blender-mcp-reference-modeling/references/workflow.md
EXTERIOR STRUCTURE GATE: build recognizable exterior structure before ornament: base/plinth, body/facade, column rhythm, openings, roof tiers, eaves, and ground contact.
STAIR AND BALUSTRADE GATE: every stair must have real treads, risers, landing slabs, side cheeks/stringers, guard posts, and a clear connection to each terrace level. Balustrades must break at stair openings and reconnect at platforms.
NO FILLER LANDSCAPE: do not add trees, people, vehicles, water, or decorative site filler unless the user explicitly asks for them.
MATERIAL REALISM GATE: separate stone, lacquered timber, glazed roof tile, metal/gold trim, and paving. Add roughness, bump/noise, edge bevels, seams, tile ribs, color variation, and weathering restrained by reference.
DELIVERY VIEWS: provide hero exterior, facade detail, roof/eave detail, and stair/terrace audit view.
使用 blender-mcp-reference-modeling 创建一个现实风格建筑外观场景。
模式：concept_spatial_modeling / exterior_architecture。重点是外观体量、结构连接、屋顶檐口、立面节奏、入口、台基楼梯、栏杆和材质细节。
EVIDENCE LEDGER: label each boundary, dimension, opening, and material as confirmed, inferred, or unknown. Do not turn weak sources into exact dimensions.
用户目标：Generate a photorealistic, volumetrically accurate exterior architectural visualization of Tiananmen Gate’s façade and immediate plinth context — emphasizing hierarchical roof composition, structural articulation of eaves and dougong, material authenticity of glazed tile, painted wood, and carved stone, and formal rhythm of columns, windows, and balustrades — without interior or functional program detail.
资料判断：建筑=high，楼层/区域=high，总体=exact_match。All key architectural identifiers —重檐歇山式屋顶 (double-eaved hip-and-gable), 多层屋顶/檐口, 斗拱, 台基 (Hanbaiyu xumi base), 栏杆 (white marble balustrade), 窗棂 (36扇菱花格式门窗), 屋顶瓦片 (yellow glazed tiles) — are consistently confirmed across multiple authoritative sources (China Daily, Wikipedia, official digital library, architectural commentary). Dimensions, proportions (9-bay x 5-jian), structural hierarchy (two-tiered massing: red platform + upper pavilion), and decorative grammar (dragon吻,仙人走兽,金龙和玺彩画) align precisely with user’s request for exterior architectural fidelity.
必须表达的空间/构件：main gate facade、upper pavilion volume、red city platform、xumi base
空间/结构关系：The xumi base (1.59m tall) supports the red platform (13m tall), which in turn carries the upper pavilion — establishing clear vertical hierarchy.；The nine-bay width (57.14m) governs horizontal rhythm of columns, windows, and balustrade bays.；Roof curvature (concave gutter line) is functionally tied to rainwater dispersion and visually lightens massive form.
视觉方向：imperial Chinese Ming-Qing transitional architecture；材质：yellow glazed ceramic roof tiles、vermillion lacquered wood、white Hanbaiyu marble (xumi base & balustrade)、gold leaf (on dougong and beam ends)；灯光：clear daylight, frontal sun angle to emphasize layered eaves and cast defined shadows on dougong and balustrade；氛围：solemn, monumental, hierarchically ordered, ceremonially austere
质量门槛：All roof layers (upper/lower eaves) must be geometrically distinct and correctly angled per歇山顶 rules.；No interior room geometry or furniture may appear; only envelope and applied ornament.；Material reflectance values must match real-world properties: matte lacquer (vermillion), specular glaze (tiles), diffuse stone (marble).；Balustrade height, spacing, and motif (lotus-and-vase) must conform to documented xumi base specifications.
提示词配方：Use photorealistic PBR materials: no stylization, no cartoon shading.；Prioritize architectural legibility over atmospheric effects — avoid fog, bloom, or lens distortion.；Ensure all roof ridges terminate in chiwen; include full set of nine beasts on main戗脊.；Render balustrade as continuous white marble element with consistent section profile and carved motifs.
交付视角：front elevation (full frame, eye-level, centered on central portal)；low-angle perspective (emphasizing vertical hierarchy: xumi base → platform → pavilion → roof)；detail close-up of dougong cluster under eastern eave (showing arch,翘,昂,斗)
按阶段执行：资料冻结和坐标设定 → 主体 blockout → 空间/结构细化 → 材质 → 灯光和相机 → 验证和交付。
未知尺寸和局部细节允许合理发挥，但要把它们作为概念推断，不要伪装成真实测量值。
输出 .blend、.glb 和至少一张预览图；导出后重新检查 GLB。
工作目录：E:\app\condex_project\Blender_create_skill\runs\gugong_corner_visual
RESEARCH TO MODEL PROMPT PACKAGE:
- target lock: 生成一个现实风格的天安门城楼外观，重点体现多层屋顶、檐口、斗拱、台基、栏杆、窗棂和屋顶瓦片细节
- build order: freeze target identity and source confidence | block out recognizable massing before small decoration | add structural connections and circulation details | add signature facade, roof, opening and edge details | apply separated realistic materials with roughness, noise and bump | render hero and close-up audit views before export
- detail targets: overall silhouette and tier proportions; base or plinth connection to the ground; entrances, doors, windows and facade rhythm; stairs with real treads, risers, landings and rail openings; guardrails split into posts, panels, caps and breaks at entrances; roof massing, eaves, ribs, tile courses, underside structure and finial details; material separation for stone, timber, roof tile, metal trim and paving
- signature feature rules: compound_roof_and_tiles => roof cannot be a single flat slab; use separate roof mass, eave underside, raised ridges and repeated tile plates or tile ribs; model main ridge, vertical ridges and diagonal hip ridges when the reference implies compound or hip roofs; stacked roof tiers must have visible support bodies, columns or bracket layers between tiers; no upper roof may float above empty air; add finial, ridge caps, eave trim and upturned corner emphasis when visible | dougong_brackets => dougong cannot be isolated cubes; build stacked bracket blocks, cantilever arms and beam seats under the eave; use at least two colors or material layers for painted bracket blocks when reference supports painted timber | ornamental_lattice_windows => windows need recessed dark glass or interior shadow, outer frame thickness, vertical bars, horizontal bars and diagonal or ornamental bars when named; avoid one simple cross when the request mentions ornamental lattice or historical window patterns | stone_balustrade_and_stairs => stairs need individual treads, risers, side cheeks, landing slabs and clear railing openings; stone balustrades need separate posts, caps, panels, relief strips and breaks at stair entrances | plinth_wall_ground_connection => ground contact needs a believable base or plinth, not a floating building body; the main body, columns and plinth must physically touch or overlap through hidden support blocks; do not leave visible shadow gaps under the building; historic wall or terrace connections need visible courses, seams, edges and material separation
- material targets: stone; timber; roof_tile; metal; glass
- negative constraints: no unrelated filler objects unless requested; no white clay final material; no single-color plastic look; no floating slabs, fake painted openings or disconnected parts; no guardrail passing through stairs or entrances
- geometry contract required components: continuous ground-contact base or plinth supporting the main body; recognizable primary body mass with real doors/windows/openings; roof system with sloped mass, eaves, ridge lines, underside support and repeated tile detail; front, roof/eave, and weak-connection audit cameras; Tiananmen city platform: white marble xumizuo is only the low base; the red city platform must be a much taller mass above it; five real arched gateway voids through the red city platform, with the center opening largest and no cutter objects left visible; upper pavilion centered on the platform with nine-bay by five-bay rhythm and red column grid; double-eaved xieshan roof built from sloped roof surfaces, lower and upper eaves, main ridge, hip ridges, ridge beasts and yellow tile courses; front identity details: national emblem, portrait/signboard zone, 36 dark lattice windows, lantern row, dougong under eaves and white marble balustrades
- geometry contract forbidden shortcuts: Do not satisfy target identity with generic boxes plus decoration.; Do not leave visible Boolean cutter objects in the exported GLB.; Do not render only close-up fragments; include a full recognizable overview.; Do not use the 1.59m xumizuo dimension as the full city-platform height.; Do not model the double-eaved xieshan roof as two flat cube slabs.; Do not export archway cutter spheres/cubes as visible objects.
- Blender modeling recipe scale policy: Keep each source dimension attached to the component it describes; never reuse a base, trim or ornament dimension as a whole-building dimension.; When exact survey dimensions are missing, preserve the visible hierarchy first: base supports body, body supports roof, openings cut through their parent mass, details sit on top.
- Blender modeling recipe component translation: Translate every confirmed or inferred must-have item into named mesh groups, not adjectives in comments.; For each signature item, build at least mass, edge/trim, and repeated-detail layers before materials.; Use object names that match the architectural role so later audit can inspect the scene.; Build Tiananmen as two dominant masses first: a tall red city platform over a separate low white marble xumizuo, then the timber pavilion above.; Build the five gateway openings as real structural voids through the red platform using pier segments/arch geometry or applied-and-deleted booleans; center opening must be largest.; Build the double-eaved xieshan roof with sloped roof planes, lower and upper eaves, main ridge, hip ridges, diagonal ridges, upturned corners, ridge ornaments and repeated yellow tile courses.; Build the pavilion facade from a nine-by-five bay rhythm: red column grid, recessed dark wall/window panels, diamond lattice bars, dougong rows under eaves, lantern row, emblem/signboard zone and balustrades.
- Blender modeling recipe procedural helpers to write: build_roof_shell; build_ridge_and_tile_rows; build_column_grid; build_facade_openings; build_stairs_and_balustrades; build_pbr_materials; build_audit_cameras; build_xieshan_roof; build_arch_gateway_row; build_linghua_lattice_windows; build_dougong_band
- Blender modeling recipe material translation: Create separate PBR-like materials for structural stone, lacquered timber, roof tile, dark openings/glass, and metal/gold trim.; Use bevels plus procedural noise/bump/color variation; do not rely on flat base colors.
- Blender modeling recipe camera translation: Render one full-building orthographic or long-lens overview that proves silhouette and ground contact.; Render close-up audit views for roof/eave, facade/openings, and stair/base connections when those features are requested.
- Blender modeling recipe audit requirements: Fail if the red city platform is not visibly taller than the white xumizuo base.; Fail if five arched gateways are only loose objects or painted marks.; Fail if the roof reads as stacked flat boards instead of double-eaved xieshan geometry.; Fail if the front overview does not show platform, pavilion and roof together.
- audit views: front elevation (full frame, eye-level, centered on central portal); low-angle perspective (emphasizing vertical hierarchy: xumi base → platform → pavilion → roof); detail close-up of dougong cluster under eastern eave (showing arch,翘,昂,斗)
- default production standard: focus on the requested building only; do not fill the scene with unrelated trees or decoration; lock the main silhouette, proportions and tier relationships before adding ornament; model real circulation parts: stairs need treads, risers, landings, side rails and clear railing openings; model guardrails as separate posts, panels, caps and directional breaks rather than continuous rings through entrances; add facade depth: columns, doors, lattice panels, plaques, brackets, eaves and visible joints; add roof depth: tiered masses, ribs, tile courses, eave trim, underside structure and finial details; use material variation: color, roughness, procedural noise and bump so the browser GLB is not a white clay model; render hero and close-up checks for overall shape, roof/eave detail, facade detail and stair/terrace detail; validate the exported GLB before publishing it to the model showcase
- evidence converted into prompt targets:
  * 承天之门——天安门城楼 - 重建后的承天门城楼 - 《城楼古景》 - 数字图书馆，智慧电子阅览室系统 :: 承天门城楼总高33.7米。它的主体建筑分为上下两层，上层是巍峨的大殿，下层是巨大的城台。承天门城楼的大殿为重檐，就是两层檐歇山式屋顶。
...
重檐歇山式屋顶的前后两坡是整坡，左右两坡是半坡，中间有一条正脊，正脊两端折下，有4条垂脊，4条戗脊，就是垂脊下端折向的一条接连殿角，两侧留有山花。
...
重檐的大殿顶上覆盖着金黄色的琉璃瓦，四角屋檐微微上翘，斜平舒展，形成漂亮的凹线形曲线，使巨大、沉重的屋顶巳得轻盈飘逸，肃穆尊贵。
...
屋顶斜面设计成凹形曲线，也有它的实用效果，下雨时，流水经过这里后，能够滴到距离墙基较远的地方去，可以保持墙基的干燥和延长建筑物的寿命。同时，后檐高高翘起，既增加了阳光照射的面积，保持了室内的亮度，又使大殿增添了奔放之感。
...
在屋顶的正脊和垂脊上，还装饰着神态各异、生动有趣的龙吻和仙人走兽，使承天门外观显得更加古雅、华丽。在红色为底的东西两侧山墙上，大面积贴金，圆圈形的叫万寿圈，呈绶带形状的为万寿带。它们相互缠绕，金光灿烂，喻示着皇帝万寿无疆、皇恩浩荡。
...
其次是歇山顶，还有
...
顶、悬山顶、硬山顶等多种形式。歇山顶也叫九脊殿，分为单檐、重檐
  * 详解天安门城楼的建筑特色 :: 天安门城楼大殿为重檐歇山式屋顶，有正脊一条，正脊的两端有一对华丽的龙型琉璃装饰物，称为龙吻（又称大吻或正吻），另有垂脊8条，在垂脊顶端各有一条龙吻，故有“九脊封十龙”的说法。
...
天安门城楼为木结构建筑，大殿飞檐下令人眼花缭乱而又排列有序的斗拱和梁枋。斗拱为我国传统木构架体系中独有，是斗形木弓形横木组成的具有翘、昂、拱特点的木制构件。梁枋又分额枋、檐枋，斗拱下面是额枋，上面彩画和金龙图案，柱子之间的构件叫檐枋，会有金龙和玺图案。
...
屋顶巨型宫灯
...
天安门城楼大殿内有60根直径为92厘米的红漆木柱，承受着屋顶建筑大部分重力。正面的36扇门窗为中国传统的菱花格式，屋顶上的天花藻井画的是团龙图案，在殿厅堂纵横交错的梁枋上绘的是金龙和玺彩绘；17盏古雅的大型宫灯，最大的那盏称为主灯，有8个面，全高6米，直径2.8米，重约450公斤；其余16盏为6个面的辅灯，每个高6米，直径2.2米，重约350公斤。每盏灯上的角各有一盏伞形小灯。
  * 1套Lumion11精品源文件 天安门城楼建筑表现-自学GO-Lumion资源中心 :: Lumion11精品源文件 天安门城楼建筑表现-
...
学GO-Lumion资源中心
...
# 1套Lumion11精品源文件 天安门城楼建筑表现

 2022-01-20 Lumion11 Lumion场景源文件 3 0 437 

 

找Lumion资源请认准自学GO网站。1套Lumion11精品源文件 天安门城楼建筑表现，Lumion11场景源文件+动画场景+参数+max模型，Lumion11文件大小：277M，供设计师学习使用。 演示视频： https://tieba.baidu.com/p/7571770869
  * 谷建华图说老北京之十一“天安门（上）”_央广网 :: 天安门是皇城的正门，城门五阙，重楼九楹，上层是重檐歇山式，黄琉璃瓦顶的巍峨城楼，东西面阔九楹，南北进深五间，取“九五”之数，象征皇帝的尊严。
...
天安门居于京城中央，建于明永乐十五年（1417年），原名“承天门”，取“承天启运”、“受命于天”之意。当时天安门是一座黄瓦飞檐、三层楼的五洞牌坊，朱漆金钉，光彩夺目。清顺治八年，改建为“天安门”，取“受命于天”、“安邦治民”之意。它有汉白玉石的须弥座，高大而色彩浓郁的墙台，上有两层重檐大楼，东西九间，南北五间，象征皇权的“九五之尊”。
...
天安门城楼为中国传统的重檐歇山顶建筑，即由四个倾斜的顶面、一条正脊、四条垂脊、四条戗脊（垂脊下端折向的一条）和两侧倾斜层面上部转折成垂直的三角形墙面组成，形成两坡和四坡屋顶的混合形式。故有“八檐九脊”之称。城楼为木结构建筑，大殿飞檐下是排列有序的斗拱和梁枋。斗拱为中国传统木构架体系中独有，是斗形木弓形横木组成的具有翘、昂、拱特点的木制构件。梁枋又分额枋、檐枋，斗拱下面是额枋，上面彩画和金龙图案，柱子之间的构件叫檐枋，会有金龙和玺图案。
...
城楼的主体建筑分为上下两层。上层是重檐歇山式，黄琉璃瓦顶
  * 详解天安门城楼的建筑特色 :: 天安门城楼大殿为重檐歇山式屋顶，有正脊一条，正脊的两端有一对华丽的龙型琉璃装饰物，称为龙吻（又称大吻或正吻），另有垂脊8条，在垂脊顶端各有一条龙吻，故有“九脊封十龙”的说法。
...
天安门城楼为木结构建筑，大殿飞檐下令人眼花缭乱而又排列有序的斗拱和梁枋。斗拱为我国传统木构架体系中独有，是斗形木弓形横木组成的具有翘、昂、拱特点的木制构件。梁枋又分额枋、檐枋，斗拱下面是额枋，上面彩画和金龙图案，柱子之间的构件叫檐枋，会有金龙和玺图案。
...
巨型宫灯
...
天安门城楼大殿内有60根直径为92厘米的红漆木柱，承受着屋顶建筑大部分重力。正面的36扇门窗为中国传统的菱花格式，屋顶上的天花藻井画的是团龙图案，在殿厅堂纵横交错的梁枋上绘的是金龙和玺彩绘；17盏古雅的大型宫灯，最大的那盏称为主灯，有8个面，全高6米，直径2.8米，重约450公斤；其余16盏为6个面的辅灯，每个高6米，直径2.2米，重约350公斤。每盏灯上的角各有一盏伞形小灯。
  * 天安门 :: 天安门坐北朝南，原通高33.7米，1970年重修后改为34.7米。建筑的底部为汉白玉精雕的须弥座，高1.59米。底座上建有朱红色的高大城台，面积约440000平米。城台的两侧有登城马道，台上建城楼。
...
城楼面阔九间（57.14米），进深五间（20.97米），重檐歇山顶，覆蓋黄琉璃瓦。在两层正檐之间有用滑轮固定的一枚中华人民共和国国徽，直径1.7米，位置与北京中轴线严密重合。屋檐下悬挂着17盏大红宫灯，其中主灯重达450公斤，辅灯也各重350公斤。整座屋顶由60根大红木柱支撑，每根柱的直径约2米。城楼的正背面各排列有36扇菱花门窗，天花、斗拱和梁枋上都绘制了最高等级的“金龙和玺”彩画。楼体的四周为回廊环绕，廊深3米左右，廊外设汉白玉栏杆和矮墙。整座天安门城楼的外观富丽堂皇，雄伟壮观，氣勢磅礡，非常莊嚴肅穆。
...
天安门城台前有金水河，河上架五座汉白玉石桥与五个门洞一一对应，称为“金水桥”。中间的桥略宽，又叫御路桥，两侧的栏杆望柱上雕刻着蟠龙图案。另外的四座桥则叫做“王公桥”，栏杆望柱上雕刻着荷花图案。在桥边还有两对石狮子，是明永乐朝的遗物。东面雄狮的右爪戏弄绣球，西面雌狮的左爪
- close-up failure checks:
  * roof close-up fails if the roof reads as one smooth board, lacks tile/ridge hierarchy, or any tier floats without support
  * facade close-up fails if bracket blocks do not visually support the eave
  * facade close-up fails if windows read as flat black rectangles with only one cross
  * stair close-up fails if stairs are a ramp, a single block, or if railings cross the stair opening
  * overview fails if the building body, columns, base, wall or terrace appear detached or hovering
硬约束：No interior spaces, no human figures, no vehicles, no modern signage or banners.；Height ratio between xumi base (1.59m), platform (13m), and pavilion (≈20m) must remain proportionally accurate.；Roof tile rows must be individually modeled and aligned to curved surface — no texture tiling alone.
不确定性：Exact number and arrangement of dougong tiers per bay (sources describe 'ordered' but not count-per-location).；Precise curvature radius of roof concavity (described qualitatively as '凹形曲线').；Color saturation of vermillion lacquer — historical pigment variation not quantified in sources.