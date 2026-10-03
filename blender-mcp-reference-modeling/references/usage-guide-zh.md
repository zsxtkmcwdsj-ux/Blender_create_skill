# 跨电脑安装与使用教程

## 1. 环境要求

- Blender 5.1 或更高版本；建议使用项目验证过的 5.2 系列或更新的兼容版本。
- Codex 或其他能够调用 Blender MCP 的代理环境。
- 已安装并启动的 Blender MCP 服务端/插件。
- 足够的磁盘空间保存阶段 `.blend`、贴图、预览图和导出文件。
- 如需优先使用材质资产，在 Blender 偏好设置中配置本地资产库。

技能不包含 Blender、MCP 插件、第三方模型、商业贴图或凭证。

## 2. 安装技能

解压后得到文件夹：

```text
blender-mcp-reference-modeling/
```

复制到：

```text
Windows: %USERPROFILE%\.codex\skills\blender-mcp-reference-modeling
macOS/Linux: ~/.codex/skills/blender-mcp-reference-modeling
```

完整退出并重启 Codex，使技能元数据重新加载。

## 3. Blender MCP 连接

1. 启动 Blender。
2. 打开 Blender MCP 插件面板并启动服务。
3. 在 Codex 中确认出现 Blender 场景查询和 Python 执行工具。
4. 先让 Codex只读查询场景信息，不要立即清空场景。
5. 若连接失败，核对 Blender 插件状态、端口、MCP 配置和防火墙；不要猜测默认端口。

## 4. 配置本地材质资产库

在 Blender 的资产库偏好中添加材质 `.blend` 所在目录。换电脑后路径通常会变化，因此不要沿用旧电脑的绝对路径。

可使用：

```powershell
blender --background --python scripts/material_library_index.py -- --roots "D:\Assets\Materials" --output "material_library_index.json"
```

根据实际 Blender 可执行文件和资产目录修改命令。

## 5. 第一次调用

在任务中明确调用：

```text
使用 $blender-mcp-reference-modeling。
先检查当前 Blender 场景和参考图，不要修改。
输出目录是……
需要交付 .blend 和 GLB。
每个阶段必须暂停确认。
材质先检查本地资产库；没有合适候选时先问我，不要直接自建。
```

随后提供：

- 参考设计板、正投影视图或尺寸表；
- 源 `.blend`（如果是继续工程）；
- 输出目录；
- 需要保留和禁止修改的内容；
- 交付格式；
- 尺寸误差和画质要求。

## 6. 推荐完整提示词

```text
使用 $blender-mcp-reference-modeling 通过 Blender MCP 搭建此场景。

参考优先级：尺寸表 > 正投影视图 > 45°效果图 > 氛围参考。
不得重新设计结构、比例、颜色和材质关系。
先另存工作文件，不覆盖源工程。
按“参考冻结、白模、结构细化、细节、材质、灯光环境、验证导出”分阶段执行；每阶段在 Blender 中可见并暂停确认。
所有平滑只使用按角度自动平滑，不使用普通平滑着色。
赋材质前先检查本地资产库并做固定机位 A/B；没有合格候选时先问我是否允许自建。
禁用一键 AI 三维生成、在线现成几何资产和冷门第三方插件。
最终交付……，误差要求……，输出目录……。
```

## 7. 检查点与恢复

建议文件命名：

```text
project_stage00_baseline.blend
project_stage01_blockout.blend
project_stage02_structure.blend
project_stage03_details.blend
project_stage04_materials.blend
project_stage05_lighting.blend
project_final_static.blend
project_cinematic.blend
```

Blender 闪退后，打开最后一个已通过验收的检查点，让技能重新核验对象数、尺寸、材质、帧范围和相机，再继续未完成阶段。

## 8. 命令行验证示例

生成场景基线：

```powershell
blender project.blend --background --python scripts/blender_scene_guard.py -- snapshot --output baseline.json
```

验证当前工程没有改变受保护内容：

```powershell
blender project.blend --background --python scripts/blender_scene_guard.py -- verify --baseline baseline.json --output verification.json
```

验证 GLB：

```powershell
blender --background --python scripts/validate_glb.py -- --glb project.glb --output project_glb_report.json
```

命令返回非零状态时，应先阅读 JSON 报告，不要继续交付。
