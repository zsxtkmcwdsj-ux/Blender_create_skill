READ CONTRACT: blender-mcp-reference-modeling/references/workflow.md
EXTERIOR STRUCTURE GATE: build recognizable exterior structure before ornament: base/plinth, body/facade, column rhythm, openings, roof tiers, eaves, and ground contact.
STAIR AND BALUSTRADE GATE: every stair must have real treads, risers, landing slabs, side cheeks/stringers, guard posts, and a clear connection to each terrace level. Balustrades must break at stair openings and reconnect at platforms.
NO FILLER LANDSCAPE: do not add trees, people, vehicles, water, or decorative site filler unless the user explicitly asks for them.
MATERIAL REALISM GATE: separate stone, lacquered timber, glazed roof tile, metal/gold trim, and paving. Add roughness, bump/noise, edge bevels, seams, tile ribs, color variation, and weathering restrained by reference.
DELIVERY VIEWS: provide hero exterior, facade detail, roof/eave detail, and stair/terrace audit view.
使用 blender-mcp-reference-modeling 创建一个现实风格建筑外观场景。
模式：concept_spatial_modeling / exterior_architecture。重点是外观体量、结构连接、屋顶檐口、立面节奏、入口、台基楼梯、栏杆和材质细节。
EVIDENCE LEDGER: label each boundary, dimension, opening, and material as confirmed, inferred, or unknown. Do not turn weak sources into exact dimensions.
用户目标：构建一个现实主义风格的天安门外部建筑场景，准确表达其作为明清皇家宫门的体量层级、结构逻辑与典型官式木构装饰语言，聚焦可被Blender几何建模与材质系统直接实现的外观特征。
资料判断：建筑=high，楼层/区域=high，总体=exact_match。所有核心外观要素（多层屋顶、檐口、斗拱、台基、栏杆、窗棂、瓦片）均在多份权威资料中明确描述并相互印证；建筑身份确认为明清皇城正门天安门，非仿建或现代变体；楼层结构明确分为下层朱红城台（含须弥座、马道、五券门）与上层重檐歇山顶城楼；视觉细节如黄琉璃瓦、菱花窗、汉白玉栏杆、莲花宝瓶栏板、斗拱形制、金龙和玺彩画等高频一致，符合‘现实风格’与‘重点体现’要求。
必须表达的空间/构件：城楼主体、城台、须弥座台基、金水桥区域
空间/结构关系：城楼主体以重檐歇山顶统摄整体垂直秩序，檐口线与斗拱层形成清晰节奏带；台基—城台—城楼构成三级抬升序列，强化中轴对称与权力象征；栏杆、窗棂、瓦片均为可参数化建模的重复性构件，需保持模数一致性
视觉方向：明清官式宫殿建筑（北京中轴线核心门阙）；材质：朱红色城墙涂料（传统矿物颜料模拟）、黄琉璃瓦（高反射率釉面，带烧制纹理）、汉白玉（细腻抛光+微凿痕）、楠木色斗拱与梁枋（暖棕底色+金箔彩绘UV贴图）、菱花窗棂（深褐色硬木+透光玻璃材质）；灯光：正午直射光（强调檐口投影与瓦垄高光），辅以柔和环境光表现彩画层次；氛围：庄严、恢弘、秩序感强，具历史厚重感与仪式性
质量门槛：所有檐口线必须符合歇山顶几何约束（四坡+两坡混合）；斗拱出跳深度与昂翘比例需符合明代官式做法（三踩或五踩，此处取五踩推定）；窗棂图案须为标准菱花纹（双交四椀或三交六椀，依据‘36扇’与‘九五之尊’推定为双交四椀）；台基与城台交接处须呈现明确收分与线脚过渡
提示词配方：使用真实比例建模（参考总高34.7m、面阔57.14m、进深20.97m）；瓦片需程序化分布（每垄瓦数、搭接量、脊饰定位精确）；斗拱组件必须独立建模并装配（非单一贴图）；材质需区分釉面反光（琉璃瓦）、漫反射（朱墙）、各向异性（木纹）；禁止添加非原始构造元素（如现代照明、广告牌、植被遮挡）
交付视角：正视图（中轴线视角，含金水桥前景）；45°斜角透视（展现重檐与斗拱立体关系）；檐口特写（斗拱+额枋+彩画+瓦作）；台基-栏杆-须弥座垂直剖面
按阶段执行：资料冻结和坐标设定 → 主体 blockout → 空间/结构细化 → 材质 → 灯光和相机 → 验证和交付。
未知尺寸和局部细节允许合理发挥，但要把它们作为概念推断，不要伪装成真实测量值。
输出 .blend、.glb 和至少一张预览图；导出后重新检查 GLB。
工作目录：E:\app\condex_project\Blender_create_skill\runs\gugong_corner_visual
RESEARCH TO MODEL PROMPT PACKAGE:
- target lock: 生成一个现实风格的天安门外观，重点体现多层屋顶、檐口、斗拱、台基、栏杆、窗棂和屋顶瓦片细节
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
- audit views: 正视图（中轴线视角，含金水桥前景）; 45°斜角透视（展现重檐与斗拱立体关系）; 檐口特写（斗拱+额枋+彩画+瓦作）; 台基-栏杆-须弥座垂直剖面
- default production standard: focus on the requested building only; do not fill the scene with unrelated trees or decoration; lock the main silhouette, proportions and tier relationships before adding ornament; model real circulation parts: stairs need treads, risers, landings, side rails and clear railing openings; model guardrails as separate posts, panels, caps and directional breaks rather than continuous rings through entrances; add facade depth: columns, doors, lattice panels, plaques, brackets, eaves and visible joints; add roof depth: tiered masses, ribs, tile courses, eave trim, underside structure and finial details; use material variation: color, roughness, procedural noise and bump so the browser GLB is not a white clay model; render hero and close-up checks for overall shape, roof/eave detail, facade detail and stair/terrace detail; validate the exported GLB before publishing it to the model showcase
- evidence converted into prompt targets:
  * 中式天安门外观su模型 - 门窗_中式门模型su模型-su模型库-sketchup网 :: 中式天安门外观su模型 - 门窗_中式门模型su模型-su模型库-sketchup网
...
# 中式天安门外观su模型
...
软 件：sketchup 大 小：1.85MB 上 传 时 间：20200114 消 耗 积 分：1
...
su模型,su素材库,3d模型,3d模型库,3d模型下载,3d模型素材,3dmax模型免费下载，cad施工图纸,3d材质贴图,沙发SU模型,椅凳SU模型,柜类SU模型,厨卫SU模型,3D沙发模型,3D陈设饰品,3D柜类模型,3D家装空间,家装CAD图纸,CAD图库,CAD节点详图,橱柜衣柜CAD图纸,CAD施工图,居住建筑效果图,工业建筑效果图,公共建筑效果图
  * Tian An Men 天安门 (259) 360 Panorama | 360Cities :: 天安门：

 天安门的主体建筑分为上下两层。

 上层是重檐歇山式，黄琉璃瓦顶的巍峨城楼，东西面阔九楹，南北进深五间，取“九五”之数，象征着皇帝的尊严。正面有36扇菱花格式门窗。城楼基座周围有汉白玉栏杆、栏板，雕刻着莲花宝瓶图案。城楼内所用木材大部分是楠木，60根红漆巨柱排列整齐，柱顶上有藻井与梁枋，绘着金龙吉祥彩画和团龙图案。地面铺的全是金砖，面积约2000平方米。屋顶的正脊与垂脊上装饰着螭吻、仙人、走兽；17盏古雅的大型宫灯，最大的那盏称为主灯，有8个面，全高6米，直径2.8米，重约450公斤，其余的16盏为6个面的辅灯，每个高6米，直径2.2米，重约350公斤。每盏灯上的角各有一盏伞形小等。
...
下层是高13米的朱红色城台，四周环绕琉璃瓦封顶的矮墙，下部是1.59米高的雕刻精美的汉白玉须弥座台基。城台的总面积达4800平方米，东西两侧各有一条长达百级供上下城楼用的梯道，俗称马道。还有5个拱形门洞，中间的门洞最大，高8.82米，宽5.25米，唯有皇帝可以进出。

 城楼前有外金水河，河上飞架7座汉白玉雕栏石桥，中间一座最宽阔的称“御路桥”，专为皇帝而设。御路桥两旁有宗室亲王过往
  * 【百年天安门】天安门的营造 :: ，是一座
...
，在牌
...
的正中高悬
...
这次重建的承天门，从形制上有一个重大的突破，即由原来的“牌坊式”变成了“宫殿式”，气势宏大，雄伟壮观，基本上具有了今日天安门的模样。
...
蒯祥提供了一个施展
...
的舞台，他大胆而巧妙地将龙纹彩绘图案运用到城
...
的装饰之中，浓烈奔放的彩绘，在红色与绿色的糅合之中，显得富丽辉
...
，形成了一个个动
...
十足的图腾。高
...
承天门大殿里的60根朱柱顶天立地，井然有序；金砖墁地，一平如纸。梁枋、斗拱、天花上一组组精美的彩画，城楼屋脊上一个个灵动的吻兽，和谐一致，相得益彰，使整个承天门尽显雍容华贵、典雅大气的皇家风范。
...
重建后的天安门，下设城台，上建城楼，重檐歇山顶。城台设5道券门，城楼面宽9间，进深5间，蕴含着封建帝王乃“九五之尊”，皇权至高无上之意。重建后的天安门总高34.4米，明间面阔8.52米，城台总宽118.99米。城楼重檐正中悬挂的匾额，由“承天门”变更为“天安门”。
...
天安门城楼为我国传统的重檐歇山顶建筑，由4个倾斜的顶面、1条正脊、4条垂脊、4条戗脊（垂脊下端折向的一条）和两侧倾斜屋面上
  * 谷建华图说老北京之十一“天安门（上）”_央广网 :: 天安门是皇城的正门，城门五阙，重楼九楹，上层是重檐歇山式，黄琉璃瓦顶的巍峨城楼，东西面阔九楹，南北进深五间，取“九五”之数，象征皇帝的尊严。
...
天安门居于京城中央，建于明永乐十五年（1417年），原名“承天门”，取“承天启运”、“受命于天”之意。当时天安门是一座黄瓦飞檐、三层楼的五洞牌坊，朱漆金钉，光彩夺目。清顺治八年，改建为“天安门”，取“受命于天”、“安邦治民”之意。它有汉白玉石的须弥座，高大而色彩浓郁的墙台，上有两层重檐大楼，东西九间，南北五间，象征皇权的“九五之尊”。
...
天安门城楼为中国传统的重檐歇山顶建筑，即由四个倾斜的顶面、一条正脊、四条垂脊、四条戗脊（垂脊下端折向的一条）和两侧倾斜层面上部转折成垂直的三角形墙面组成，形成两坡和四坡屋顶的混合形式。故有“八檐九脊”之称。城楼为木结构建筑，大殿飞檐下是排列有序的斗拱和梁枋。斗拱为中国传统木构架体系中独有，是斗形木弓形横木组成的具有翘、昂、拱特点的木制构件。梁枋又分额枋、檐枋，斗拱下面是额枋，上面彩画和金龙图案，柱子之间的构件叫檐枋，会有金龙和玺图案。
...
城楼的主体建筑分为上下两层。上层是重檐歇山式，黄琉璃瓦顶
  * BlueWalking/Tiananmen-Square-3D :: 我们到底有多爱北京天安门呢，爱到我们为他用OpenGL做了一个3D虚拟场景模型。下面是实验题目概况。
...
设计天安门广场的3D景物模型，建立形体的参数模型。采用图形的几何变换方法将所定义物体的投影图绘制出来，再使用光照和纹理等技术，增加其真实感效果。
...
景物模型中可以设计有多种元素，尽量使设计出的场景与真实模型匹配，以丰富实验效果。本实验中设计有如下模型：
...
建筑模型：天安门、人民英雄纪念碑、毛主席纪念堂、中国国家博物馆、人民大会堂、正阳门。

移动模型：太阳、月亮、小人游客和雪花。

装饰模型：花坛、树木和告示牌。

其他模型：马路和旗杆。
...
在具有真实感的场景中，除了应该设计模型以外，还应该对场景和模型加以处理，以增强它的真实感，赋予它生命。本实验中用到了如下技术完善场景效果：
...
光照模型，材质属性，纹理贴图，天空盒。
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
硬约束：不得简化或省略任何一层屋顶结构；不得合并或模糊台基、城台、城楼三重水平界面；斗拱必须可见且符合‘排列有序’描述（非装饰性浮雕）；栏杆须完整环绕城台顶部（非仅正面）；窗棂必须为菱花式，不可替换为直棂或支摘窗
不确定性：具体斗拱出踩数（文献未明示，依九间规模推定为五踩）；瓦件尺寸与铺法（无精确数据，按清代官式《工程做法则例》常规推定）；须弥座束腰部分雕饰密度（仅知‘莲花宝瓶’，未说明单元间距）；城台侧壁马道收口细部（仅知‘长达百级’，无台阶断面尺寸）