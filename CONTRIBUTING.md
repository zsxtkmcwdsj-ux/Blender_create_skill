# 协作编辑

在仓库页面将地址中的 `github.com` 改成 `github.dev`，即可打开浏览器编辑器。
使用自己的 GitHub 账号登录后，可以编辑 Python、HTML、Markdown 和 JSON 等文本文件。

有仓库写入权限的协作者可以在分支上提交修改并发起 Pull Request。
公开仓库的其他参与者可以先 Fork 到自己的账号，再编辑、提交并向原仓库发起 Pull Request。
私有仓库的参与者需要先获得仓库所有者邀请。

`.blend`、`.glb` 等模型文件需要下载到本机，通过 Blender 或相应三维工具编辑后提交。
浏览器编辑器用于代码修改；运行 Python 服务和 Blender 建模需要本地运行环境。

请勿提交 `.env`、API 密钥、虚拟环境、日志或模型权重。
配置时复制 `.env.example` 为 `.env`，并在本机填写密钥。
