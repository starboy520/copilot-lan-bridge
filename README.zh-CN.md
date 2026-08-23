# Copilot LAN Bridge (Python)

一个跨平台的本地网关，让同一局域网内其他机器上的 Codex CLI 使用服务端机器已有的 GitHub Copilot 登录。

首版支持：

- OpenAI `GET /v1/models`
- OpenAI `POST /v1/responses`
- 普通响应和 SSE 流式响应透传
- OpenCode `github-copilot` OAuth 凭据
- 局域网 Bearer API Key 鉴权
- Windows、macOS 和 Linux

当前只暴露 Copilot 原生支持 `/responses` 的模型。仅支持 `/v1/messages` 的 Claude 模型暂不暴露，后续需要增加 Anthropic Messages 协议适配层。

## Linux / WSL 部署

需要 Python 3.11 或更高版本。先安装 OpenCode 并登录 Copilot；如果已经准备好 `auth.json`，可以跳过登录步骤：

```bash
curl -fsSL https://opencode.ai/install | bash
opencode auth login --provider "GitHub Copilot" --method "Login with GitHub Copilot"
```

建立 Python 环境：

```bash
git clone https://github.com/starboy520/copilot-lan-bridge.git ~/copilot-lan-bridge
cd ~/copilot-lan-bridge
sudo apt-get update
sudo apt-get install -y python3-venv
python3 -m venv ~/.venvs/copilot-lan-bridge
~/.venvs/copilot-lan-bridge/bin/python -m pip install -e .
```

直接启动：

```bash
bash ~/copilot-lan-bridge/scripts/run-wsl.sh
```

尽管脚本名为 `run-wsl.sh`，它也适用于原生 Linux。脚本默认监听 `0.0.0.0:18787`，并在 `~/.config/copilot-lan-bridge/api-key` 生成 64 位十六进制访问密钥；目录权限为 `700`，文件权限为 `600`。

只允许本机或 SSH 隧道访问时，限制监听地址：

```bash
COPILOT_BRIDGE_HOST=127.0.0.1 bash ~/copilot-lan-bridge/scripts/run-wsl.sh
```

作为 systemd 服务运行：

```bash
mkdir -p ~/.config/systemd/user
cp ~/copilot-lan-bridge/scripts/copilot-lan-bridge.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now copilot-lan-bridge
```

WSL2 NAT 模式还需要在管理员 PowerShell 中执行：

```powershell
Set-Location C:\path\to\copilot-lan-bridge
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-windows-lan.ps1
```

WSL 的内部 IP 在 WSL 完全重启后可能变化。发生重启后重新执行上面的 PowerShell 脚本即可刷新端口转发。

## Windows 原生部署

需要 Python 3.11 或更高版本，并准备好 OpenCode GitHub Copilot 凭据。在 PowerShell 中执行：

```powershell
git clone https://github.com/starboy520/copilot-lan-bridge.git "$HOME\copilot-lan-bridge"
Set-Location "$HOME\copilot-lan-bridge"
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

如果 `py -3.11` 不可用，但 `python --version` 是 3.11 或更高版本，可以改用 `python -m venv .venv`。

生成并保存一个 Bridge API Key：

```powershell
$configDir = Join-Path $HOME ".config\copilot-lan-bridge"
New-Item -ItemType Directory -Force $configDir | Out-Null
$keyBytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($keyBytes)
$bridgeKey = [Convert]::ToHexString($keyBytes).ToLower()
Set-Content -NoNewline -Encoding ascii (Join-Path $configDir "api-key") $bridgeKey
```

启动服务：

```powershell
$env:COPILOT_BRIDGE_HOST = "0.0.0.0"
$env:COPILOT_BRIDGE_PORT = "18787"
$env:COPILOT_BRIDGE_API_KEY = Get-Content -Raw "$HOME\.config\copilot-lan-bridge\api-key"
# 自动检测失败时再设置：
# $env:OPENCODE_AUTH_FILE = "$HOME\.local\share\opencode\auth.json"
& ".\.venv\Scripts\copilot-lan-bridge.exe"
```

Windows 防火墙只允许“专用网络”访问 TCP 18787。需要管理员 PowerShell：

```powershell
New-NetFirewallRule -DisplayName "Copilot LAN Bridge" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 18787 -RemoteAddress LocalSubnet -Profile Private
```

用 `ipconfig` 找到服务端局域网 IPv4 地址，例如 `192.168.1.20`。健康检查无需密钥：

```powershell
Invoke-RestMethod http://192.168.1.20:18787/health
```

`/health` 无需密钥；`/v1/models` 和 `/v1/responses` 必须携带 Bridge API Key。

## 客户端 Codex 配置

在其他机器的 `~/.codex/config.toml` 中加入：

```toml
model_provider = "copilot_lan"

[model_providers.copilot_lan]
name = "Copilot LAN Bridge"
base_url = "http://192.168.1.20:18787/v1"
env_key = "COPILOT_BRIDGE_API_KEY"
wire_api = "responses"
```

把服务端生成的同一个密钥放入客户端环境变量，然后运行 Codex：

Linux/macOS：

```bash
export COPILOT_BRIDGE_API_KEY="服务端生成的密钥"
codex
```

Windows PowerShell：

```powershell
$env:COPILOT_BRIDGE_API_KEY = "服务端生成的密钥"
codex
```

`env_key` 填写的是环境变量名称，不是密钥值或文件路径。环境变量只会由父进程传给新进程；设置后需要重新启动 Codex，已经运行的 Codex、VS Code 或 Node 进程不会自动获得它。

### 直接读取 API Key 文件（推荐）

较新的 Codex CLI 支持命令鉴权，可以在每次启动时直接读取 Bridge API Key 文件，不需要设置环境变量。Linux/WSL 客户端配置示例：

```toml
model_provider = "copilot_lan"

[model_providers.copilot_lan]
name = "Copilot LAN Bridge"
base_url = "http://127.0.0.1:18787/v1"
wire_api = "responses"

[model_providers.copilot_lan.auth]
command = "/usr/bin/cat"
args = ["/home/qichengjie/.config/copilot-lan-bridge/api-key"]
```

Windows 客户端可以使用：

```toml
[model_providers.copilot_lan.auth]
command = "cmd.exe"
args = ["/d", "/c", "type", 'C:\Users\your-user\.config\copilot-lan-bridge\api-key']
```

使用时请注意：

- 将示例路径替换为客户端上 `api-key` 文件的实际绝对路径。
- 使用命令鉴权时，不要再配置 `env_key`，两种鉴权方式不能同时使用。
- Linux/WSL 上执行 `chmod 600 ~/.config/copilot-lan-bridge/api-key`，避免其他用户读取密钥。
- 如果 Codex 与桥接服务不在同一台机器，只复制 Bridge API Key 文件，不要把 OpenCode `auth.json` 复制到客户端。

可先验证模型接口：

```powershell
$headers = @{ Authorization = "Bearer $env:COPILOT_BRIDGE_API_KEY" }
Invoke-RestMethod -Headers $headers http://192.168.1.20:18787/v1/models
```

## 通过 SSH 隧道访问

跨公网使用时，建议让桥接服务只监听 `127.0.0.1`，再从客户端建立加密隧道：

```bash
ssh -p 22 -N \
	-L 127.0.0.1:18787:127.0.0.1:18787 \
	user@example.com
```

此时 Codex 使用 `base_url = "http://127.0.0.1:18787/v1"`，无需把 18787 端口直接暴露到公网。

## 在其他机器复用登录

桥接器使用两种不同的凭据：

- `~/.local/share/opencode/auth.json` 是 GitHub Copilot OAuth 凭据，桥接服务用它访问 GitHub Copilot。
- `~/.config/copilot-lan-bridge/api-key` 是桥接器自己的访问密钥，Codex 客户端用它访问桥接服务。

### 其他机器只运行 Codex

只需把桥接器访问密钥配置到客户端，不需要再次登录 GitHub Copilot，也不要复制 OAuth 文件：

```powershell
[Environment]::SetEnvironmentVariable(
	"COPILOT_BRIDGE_API_KEY",
	"服务端当前使用的桥接密钥",
	"User"
)
```

客户端请求仍由原服务端转发，所有机器共同使用服务端 GitHub Copilot 账号的额度。

### 其他机器也运行桥接服务

仅复制桥接访问密钥不够，因为它不能用于登录 GitHub Copilot。若不想在新服务器上再次执行设备登录，需要通过 `scp`、受保护的 U 盘或其他安全通道复制以下两个文件：

```text
~/.local/share/opencode/auth.json
~/.config/copilot-lan-bridge/api-key
```

复制后在新 Linux/WSL 服务器上修正权限：

```bash
mkdir -p ~/.local/share/opencode ~/.config/copilot-lan-bridge
chmod 700 ~/.local/share/opencode ~/.config/copilot-lan-bridge
chmod 600 ~/.local/share/opencode/auth.json
chmod 600 ~/.config/copilot-lan-bridge/api-key
```

之后安装并启动桥接器即可，不需要再次执行 GitHub Device Login。多台桥接器可以共用同一个 OAuth，但它们会共同消耗同一个 Copilot 账号的额度；如果 GitHub 撤销授权、凭据过期或账号主动退出，则需要重新登录。

## 测试

测试核心配置、鉴权、凭据解析和模型过滤，不需要真实 Copilot 请求：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## 安全边界

- Copilot OAuth token 只保留在服务端；客户端只拿到桥接器自己的 API Key。
- `auth.json` 和 `api-key` 都不能提交到 Git、上传到 GitHub、粘贴到聊天或通过明文邮件传输；OAuth 文件比桥接访问密钥更敏感。
- 非回环监听时，程序拒绝使用空密钥或少于 32 字符的密钥。
- 当前局域网连接是 HTTP，API Key 在传输中没有加密。只应在可信专用网络使用；跨不可信网络应放在 Tailscale/WireGuard 内，或在前面部署 HTTPS 反向代理。
- API Key 只能限制谁能访问，不能为不同客户端分别计算 Copilot 配额。
