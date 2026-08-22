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

## WSL 部署

当前项目已在 Ubuntu 24.04 WSL2 验证。先安装 OpenCode 并登录 Copilot：

```bash
curl -fsSL https://opencode.ai/install | bash
opencode auth login --provider "GitHub Copilot" --method "Login with GitHub Copilot"
```

建立 Python 环境：

```bash
git clone https://github.com/starboy520/copilot-lan-bridge.git ~/copilot-lan-bridge
cd ~/copilot-lan-bridge
sudo apt-get update
sudo apt-get install -y python3.12-venv
python3 -m venv ~/.venvs/copilot-lan-bridge
~/.venvs/copilot-lan-bridge/bin/pip install -e .
```

直接启动：

```bash
bash ~/copilot-lan-bridge/scripts/run-wsl.sh
```

脚本会在 `~/.config/copilot-lan-bridge/api-key` 生成 64 位十六进制访问密钥，目录权限为 `700`，文件权限为 `600`。

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

## 服务端安装

需要 Python 3.11 或更高版本，并先通过 OpenCode 登录 GitHub Copilot。

```powershell
cd python-bridge
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

生成一个局域网访问密钥：

```powershell
$keyBytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($keyBytes)
[Convert]::ToHexString($keyBytes).ToLower()
```

启动服务：

```powershell
$env:COPILOT_BRIDGE_HOST = "0.0.0.0"
$env:COPILOT_BRIDGE_PORT = "18787"
$env:COPILOT_BRIDGE_API_KEY = "上一步生成的密钥"
# 自动检测失败时再设置：
# $env:OPENCODE_AUTH_FILE = "$HOME\.local\share\opencode\auth.json"
copilot-lan-bridge
```

Windows 防火墙只允许“专用网络”访问 TCP 18787。需要管理员 PowerShell：

```powershell
New-NetFirewallRule -DisplayName "Copilot LAN Bridge" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 18787 -Profile Private
```

用 `ipconfig` 找到服务端局域网 IPv4 地址，例如 `192.168.1.20`。健康检查无需密钥：

```powershell
Invoke-RestMethod http://192.168.1.20:18787/health
```

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

```powershell
$env:COPILOT_BRIDGE_API_KEY = "服务端生成的密钥"
codex
```

可先验证模型接口：

```powershell
$headers = @{ Authorization = "Bearer $env:COPILOT_BRIDGE_API_KEY" }
Invoke-RestMethod -Headers $headers http://192.168.1.20:18787/v1/models
```

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