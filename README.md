# Copilot LAN Bridge

Cross-platform Python gateway that lets Codex clients use GitHub Copilot models through an OpenAI Responses-compatible API.

- OpenAI-compatible `GET /v1/models` and `POST /v1/responses`
- Native Responses passthrough and Chat Completions adaptation, including Gemini
- Streaming SSE, text/image inputs, function calls, and custom tools
- OpenCode GitHub Copilot OAuth credentials
- Bearer authentication for LAN clients
- Windows, WSL, macOS, and Linux support

Clients continue to use `/v1/responses`. The bridge prefers native `/responses` support and otherwise converts requests and replies through Copilot's `/chat/completions` endpoint. Chat adaptation requires full conversation history in `input`; `previous_response_id` and other server-side conversation state are unsupported. Custom tools are wrapped as functions with a string `input` argument. Image generation tools are omitted. Codex's default hosted web search declarations are also omitted, and the model is told that hosted search is unavailable. Explicit search tool selection, other hosted tools, and unsupported input types return an error. Models that support only Anthropic Messages remain unavailable.

The HTTP request body limit is 100 MiB (approximately 104.9 MB), allowing requests larger than aiohttp's default 1 MiB. Requests over the limit receive HTTP 413 before any upstream model request.

Codex's model menu uses its own catalog; updating `/v1/models` does not automatically update that menu. On the Codex client, use the Python environment where this package is installed and ensure Codex CLI is on `PATH`:

```bash
python -m copilot_lan_bridge.codex_catalog \
  --base-url http://192.168.1.20:18787/v1 \
  --api-key-file ~/.config/copilot-lan-bridge/api-key \
  --output ~/.codex/copilot-models.json
```

Set `model_catalog_json = "/home/your-user/.codex/copilot-models.json"` at the top level of `~/.codex/config.toml`, before any table headers, using the output file's absolute path. Restart Codex. After updating a remote bridge, run the export again on each client and restart Codex to refresh its menu.

[完整中文安装与部署文档](README.zh-CN.md)

> Keep `auth.json`, bridge API keys, `.env` files, and logs out of Git. Use this gateway only in accordance with your GitHub Copilot plan and applicable terms.
