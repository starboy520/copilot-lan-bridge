# 小问号学习助手

面向小朋友的家庭学习 Web 应用，支持连续对话、拍照讲题、作业批改、分步提示、答案检查、数学公式和 C++ 代码讲解。模型请求由 Python 后端转发到 `copilot-lan-bridge`，浏览器不会接触 bridge 密钥。

支持多个孩子档案：每个孩子拥有独立的聊天记录和学习设置，全家共用一个家庭密码。首次升级到档案版本时，原有聊天和设置会自动归入“孩子”默认档案。

首次打开会要求设置一个 8—64 字符的家庭密码。之后每台设备必须登录才能访问聊天、档案、设置和题目图片；连续输错 5 次会暂时锁定。登录后可在“家长与学习设置”中输入两次新密码直接重置，整个应用只使用这一套密码。

如果已经无法登录，可在服务器终端交互式重置家庭密码（密码不会出现在命令历史中）：

```bash
cd ~/copilot-lan-bridge/study-agent
python3 -m server.app --reset-family-password
# Docker 部署：docker compose exec study-agent python3 -m server.app --reset-family-password
```

## 快速开始（Windows）

运行条件：Windows 10/11、Python 3.10+，以及已经启动的 `copilot-lan-bridge`。

1. 双击 `启动学习助手.cmd`。
2. 电脑访问 `http://127.0.0.1:8765`。
3. 手机与电脑连接同一 Wi-Fi，使用启动窗口显示的局域网地址。

启动脚本会优先读取 `COPILOT_BRIDGE_API_KEY`；没有设置时，会尝试从 WSL 的 `~/.config/copilot-lan-bridge/api-key` 读取。Windows 防火墙询问时只允许“专用网络”。

## 迁移到另一台 Windows 电脑

1. 复制整个项目目录；如需保留聊天记录，也复制 `data`。
2. 安装 Python 3.10 或更高版本，并确认 `py -3.10 --version` 可用。
3. 在新电脑上启动 bridge。
4. 设置密钥后启动：

```powershell
$env:COPILOT_BRIDGE_URL = "http://127.0.0.1:18787"
$env:COPILOT_BRIDGE_API_KEY = "你的 bridge 密钥"
.\启动学习助手.ps1
```

密钥只应放在环境变量或私有配置中，不要写进源码或提交到 Git。

## Linux / NAS 直接运行

成品运行只依赖 Python 标准库，不需要安装 Node.js 或 Python 第三方包：

```bash
cp .env.example .env
# 编辑 .env；非 Docker 部署通常将 COPILOT_BRIDGE_URL 改为 http://127.0.0.1:18787
chmod +x start.sh
./start.sh
```

### Linux 开机自启动

如果仓库位于 `~/copilot-lan-bridge`，可以像 bridge 一样安装为当前用户的 systemd 服务：

```bash
cd ~/copilot-lan-bridge/study-agent
chmod +x scripts/install-linux-service.sh
./scripts/install-linux-service.sh
```

安装后可用以下命令查看状态和日志：

```bash
systemctl --user status study-agent.service
journalctl --user -u study-agent.service -f
```

服务会在 `copilot-lan-bridge.service` 之后启动，异常退出时自动重启。如果安装脚本提示需要启用 linger，请按提示执行一次 `sudo loginctl enable-linger "$USER"`，这样无需登录也能开机启动。

如果 bridge 位于另一台机器，`COPILOT_BRIDGE_URL` 必须填写学习助手服务器能够访问的地址，并在防火墙上只允许两台服务器之间通信。

## Docker / Compose

```bash
cp .env.example .env
# 编辑 .env，填写 bridge 地址和密钥
docker compose up -d --build
docker compose logs -f study-agent
```

默认只发布到服务器的 `127.0.0.1:8765`，适合配合 HTTPS 反向代理。如果只在可信家庭局域网使用，可将 `compose.yaml` 中的端口改为 `8765:8765`。

Docker 中的 `127.0.0.1` 指容器自身。bridge 在宿主机时，Docker Desktop 通常使用 `http://host.docker.internal:18787`；Linux 还必须确保 bridge 监听 Docker 可达的宿主机接口，并用防火墙限制来源，不能把 bridge 端口直接暴露到公网。

Compose 使用名为 `study-agent-data` 的 Docker volume 保存数据库和图片，重建容器不会清空数据。

验证部署：

```bash
curl http://127.0.0.1:8765/api/health
```

返回的 `bridge` 应为 `true`。

## 公网部署

当前版本提供共享家庭密码准入，但仍定位于可信家庭网络，不能直接把 `8765` 端口映射到公网。公网使用至少需要：

- Nginx、Caddy 等 HTTPS 反向代理；
- 根据实际风险增加独立账号或 VPN 准入（推荐 Tailscale/ZeroTier）；
- 请求限流、访问日志和异常告警；
- 防火墙禁止公网直接访问 bridge；
- 定期备份并限制 `data` 目录访问权限。

仅配置 HTTPS 或共享密码并不等于已经具备公网安全性。反向代理使用 HTTPS 时应传递 `X-Forwarded-Proto: https`，后端会为登录 Cookie 加上 `Secure` 属性。

## 配置项

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `COPILOT_BRIDGE_URL` | `http://127.0.0.1:18787` | 后端可访问的 bridge 地址 |
| `COPILOT_BRIDGE_API_KEY` | 空 | bridge 密钥；Windows 启动脚本可尝试从 WSL 读取 |
| `STUDY_AGENT_MODEL` | `gpt-5.6-sol` | 全新数据目录的初始模型 |
| `STUDY_AGENT_HOST` | `127.0.0.1` | Web 监听地址；启动脚本和容器使用 `0.0.0.0` |
| `STUDY_AGENT_PORT` | `8765` | Web 端口 |
| `STUDY_AGENT_DATA_DIR` | 项目内 `data` | SQLite、设置和题目图片目录 |

模型与思考深度也可在“家长与学习设置”中调整。数据库已有保存值时，保存值优先于 `STUDY_AGENT_MODEL`。

## 数据、备份与升级

直接运行时，`data/study-agent.db` 保存聊天和设置，`data/attachments` 保存题目图片。停掉服务后复制整个 `data` 目录即可完成一致性备份；恢复时覆盖目标部署的 `data` 目录。Docker 部署则备份 `study-agent-data` volume。

升级步骤：

1. 备份 `data`。
2. 替换程序文件，但保留原 `data` 和 `.env`。
3. Docker 使用 `docker compose up -d --build`；直接运行则重启进程。
4. 检查 `/api/health`，再做一次文字和图片提问。

不要公开、同步或提交 `data`、`.env` 和 bridge 密钥。

## 功能与边界

- 支持流式对话、单张图片、Markdown、LaTeX、C++、历史记录和响应式页面。
- 支持引导、直接讲解和批改作业模式，以及学段、回答详略、模型和思考深度设置。
- 批改作业模式可直接上传图片，逐题判断、指出第一处错误并给出订正建议；看不清或缺少作答时会明确提示。
- 支持最多 8 个孩子档案，可切换、重命名和删除；统一由家庭密码保护访问。
- 支持共享家庭密码登录、HttpOnly 会话 Cookie、退出登录和连续输错限制。
- 图片支持 JPG、PNG、WebP；原图 15 MB 以内，压缩后不超过 3 MB。
- 图片默认保存七天后清理。
- 不联网搜索，不执行模型生成的代码或系统命令。

## 开发与测试

仅重新构建前端时需要 Node.js 与 pnpm：

```powershell
pnpm install
pnpm build
py -3.10 -m unittest discover -s tests -v
```

开发模式可运行 `pnpm dev`；Vite 会把 `/api` 转发到 `127.0.0.1:8765`。
