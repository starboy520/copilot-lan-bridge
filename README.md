# Copilot LAN Bridge

Cross-platform Python gateway that lets Codex clients use GitHub Copilot models through an OpenAI Responses-compatible API.

- OpenAI-compatible `GET /v1/models` and `POST /v1/responses`
- Streaming SSE passthrough
- OpenCode GitHub Copilot OAuth credentials
- Bearer authentication for LAN clients
- Windows, WSL, macOS, and Linux support

[完整中文安装与部署文档](README.zh-CN.md)

> Keep `auth.json`, bridge API keys, `.env` files, and logs out of Git. Use this gateway only in accordance with your GitHub Copilot plan and applicable terms.