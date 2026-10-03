# Research-to-Blender

这是一个独立的轻量工作流：只把 Agent-reach 的调研能力接到 `blender-mcp-reference-modeling`，不复用旧建筑项目的空间 schema、布局器或 Blender 生成代码。

```text
自然语言需求
-> Agent-reach: Exa / 小红书 / 百度百科
-> 大模型: 判断目标建筑和资料相关性
-> scene_brief.json
-> skill_prompt.md
-> blender-mcp-reference-modeling
-> .blend / .glb / 预览图
```

## 使用

先配置 `.env`，再运行：

```powershell
Copy-Item .env.example .env
python .\run_scene_workflow.py --question "做一个现代图书馆公共阅读区，包含入口大厅、阅读区、服务台、走廊、楼梯和电梯" --case-id library_concept
```

没有 API 或只想检查流程时：

```powershell
python .\run_scene_workflow.py --question "做一个低多边形咖啡店室内场景" --case-id cafe_concept --offline
```

生成后，把对应 case 的 `skill_prompt.md` 和 `research.json` 交给 `$blender-mcp-reference-modeling`。skill 负责真正的 Blender 分阶段建模、材质、灯光、相机、导出和验证。

## 输出

```text
runs/<case_id>/
  research.json       Agent-reach 统一调研结果
  synthesis_raw.json  大模型原始简报判断（有 API 时）
  scene_brief.json    目标验证、空间、关系、风格和不确定性
  skill_prompt.md     给 Blender skill 的综合提示词
  handoff.json        交接清单
```

## Single-room architecture mode

For a single enclosed room, the workflow now uses a continuous-shell contract:

- build the complete floor, walls, wall thickness, and ceiling before furniture;
- create real wall openings before inserting doors and windows;
- verify the opening from both sides and in section view;
- apply floor, wall, ceiling, skirting, frame, threshold/sill, and source-driven light as the minimum hard finish;
- keep sockets, HVAC, detectors, sprinklers, drains, waterproofing, acoustic panels, and curtains conditional on evidence or room type;
- deliver an exterior/door view and an interior/window view, then audit missing elements and inferred dimensions.

The detailed contract is in `blender-mcp-reference-modeling/references/closed-space-hard-finish.md`.

## Explicit interior/exterior module

Do not rely on keyword guessing for scene type. Choose the generation module at the workflow entry:

```powershell
python .\run_scene_workflow.py --question "生成祈年殿外观，重点屋顶、台基、楼梯和栏杆" --case-id qiniandian_exterior --module exterior --offline
python .\run_scene_workflow.py --question "生成一个会议室，封闭空间，包含门窗和基础硬装" --case-id meeting_room --module interior --offline
```

`--module exterior` adds exterior structure gates: recognizable massing, roof/eave system, facade rhythm, real stairs with landings, balustrade openings at stairs, connected terrace levels, material bump/roughness variation, and no unrelated landscaping unless requested.

It also adds prompt directives learned from the Qiniandian iteration: staged exterior recipe, explicit must-have components, close-view detail targets, negative constraints, and an audit render for the weakest structural area.

`--module interior` keeps the continuous-shell and hard-finish gates for rooms: complete floor/walls/ceiling, real door/window holes, frames, thresholds/sills, lighting, and adjacency checks.

默认模式是概念空间建模：主要表达布局、排布、动线和空间氛围，不要求真实建筑一比一复刻。

## 传统窗棂图片到三维模型

`lattice_studio.html` 已形成独立的“图片 → 结构 → 2.5D 模型”流程。原有文字生成建筑功能不受影响。

当前版本支持：

- 上传 PNG、JPEG 或 WebP 窗棂图片；
- 支持三种范围方式：自由多边形圈选、矩形四角透视矫正、直接使用整图；
- 输入一个真实窗框宽度；
- 可在真实窗棂木条上点击3—5处进行颜色取样；
- 自动判断深色或浅色窗棂；支持分别取样窗棂正样本和植物、假山、石头、墙面等背景负样本；
- 浏览器端完成选区裁切/透视矫正、自动分割、中心线骨架与节点连线提取；
- 在分割图上用“补成实体/擦成背景”笔刷修正识别结果；
- 一键保留窗框相连的主结构，去除孤立假山轮廓；支持去除小杂点、连接小断点、黑白反转，并要求人工确认分割；
- 把确认后的实体轮廓保存为 PNG、SVG 和 JSON；
- 后台调用本机 Blender，将白色实体按真实长宽与输入进深挤出为 2.5D 模型；
- 输出 `.blend`、`.glb`、正视图、透视图、几何报告和 GLB 独立重导入校验报告；
- 不依赖 OpenCV、NumPy 或 Pillow。

推荐操作顺序：

1. 上传照片；不规则窗棂选择“自由轮廓圈选”，沿外边界点击并完成轮廓。
2. 矩形斜拍照片可选择“四角透视矫正”；背景已经干净时也可直接使用整图。
3. 填写窗框真实宽度；点击“取样窗棂颜色”，在木条上选3—5处。
4. 点击“取样背景干扰”，分别在植物、假山、石头或墙面上取样；不同颜色的干扰物应各取1—3处。
5. 保持“自动判断”和背景抑制开启，然后点击“分析图片”；可用“背景排除容差”控制排除强度。
6. 检查“实体分割修正”：白色只能是外框和窗棂。孤立误识别可先点“只保留主结构”，其余用笔刷擦除。
7. 点击“确认分割并保存”。
8. 点击“生成三维模型”，等待 Blender 生成并完成 GLB 校验。
9. 在右侧成果列表打开 Blender、GLB、预览图或模型展示台。

这里的三维结果属于单张正面照片驱动的 **2.5D 轮廓挤出**。它适合孔隙率、遮阳和初步采光实验，但不能恢复照片中看不到的榫卯、雕刻截面、背面或真实材料。

macOS 可双击 `start_workflow_studio.command`，也可以在项目目录运行：

```bash
python3 workflow_server.py --host 127.0.0.1 --port 8765
```

然后打开：

```text
http://127.0.0.1:8765/lattice_studio.html
```

直接双击 HTML 也能在浏览器中分析图片和下载 JSON，但只有通过本地服务打开时，结果才会自动保存到 `runs/<case_id>/`。
