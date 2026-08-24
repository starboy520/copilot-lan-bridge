import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import {
  BookOpen,
  Camera,
  Check,
  ChevronLeft,
  CircleStop,
  Code2,
  ImagePlus,
  Lightbulb,
  Menu,
  MessageCircleQuestion,
  Plus,
  RotateCcw,
  Send,
  Settings,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { takeNdjsonLines } from "./stream.js";

const QUICK_ACTIONS = [
  { label: "给我一点提示", icon: Lightbulb, prompt: "请先给我一个小提示，不要直接公布完整答案。" },
  { label: "分步骤讲解", icon: BookOpen, prompt: "请把这道题分成容易理解的小步骤讲解。" },
  { label: "检查我的答案", icon: Check, prompt: "我想检查自己的答案。请先问我做到了哪一步，再帮我找第一个错误。" },
  { label: "再出一道类似题", icon: RotateCcw, prompt: "请根据刚才的知识点再出一道难度相近的题，暂时不要给答案。" },
];

const STARTERS = [
  { icon: Lightbulb, title: "启发思考", text: "帮我理解质数，不要直接背定义" },
  { icon: Camera, title: "拍照讲题", text: "拍下题目，我会先确认题意再讲解" },
  { icon: Code2, title: "代码学习", text: "帮我看看这段 C++ 哪里写错了" },
];

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "请求失败，请稍后重试。 ");
  return data;
}

function formatSessionTime(value) {
  if (!value) return "";
  const date = new Date(value);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

async function compressImage(file) {
  if (!file.type.match(/^image\/(jpeg|png|webp)$/)) {
    throw new Error("请选择 JPG、PNG 或 WebP 图片。 ");
  }
  if (file.size > 15 * 1024 * 1024) throw new Error("原图太大，请选择 15 MB 以内的图片。 ");
  const source = await createImageBitmap(file);
  const maxSide = 1800;
  const scale = Math.min(1, maxSide / Math.max(source.width, source.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(source.width * scale));
  canvas.height = Math.max(1, Math.round(source.height * scale));
  const context = canvas.getContext("2d");
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(source, 0, 0, canvas.width, canvas.height);
  source.close();

  let quality = 0.88;
  let blob;
  do {
    blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
    quality -= 0.1;
  } while (blob && blob.size > 2.8 * 1024 * 1024 && quality >= 0.48);
  if (!blob || blob.size > 3 * 1024 * 1024) throw new Error("图片压缩后仍然过大，请重新拍摄。 ");
  return await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("无法读取图片。"));
    reader.readAsDataURL(blob);
  });
}

function MarkdownMessage({ children }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={{
        a: ({ href, children: label }) => <a href={href} target="_blank" rel="noreferrer">{label}</a>,
        pre: ({ children: content }) => <pre tabIndex="0">{content}</pre>,
      }}
    >
      {children}
    </ReactMarkdown>
  );
}

function Sidebar({ open, sessions, activeId, onSelect, onNew, onDelete, onSettings, onClose }) {
  return (
    <>
      {open && <button className="sidebar-backdrop" aria-label="关闭会话列表" onClick={onClose} />}
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <div className="brand-row">
          <div className="brand-mark"><MessageCircleQuestion size={22} /></div>
          <div><strong>小问号</strong><span>学习助手</span></div>
          <button className="icon-button sidebar-close" onClick={onClose} aria-label="关闭"><X size={20} /></button>
        </div>
        <button className="new-chat-button" onClick={onNew}><Plus size={18} />新对话</button>
        <div className="section-label">最近对话</div>
        <nav className="session-list" aria-label="历史会话">
          {sessions.length === 0 && <p className="empty-sessions">开始第一次提问吧</p>}
          {sessions.map((session) => (
            <div className={`session-row ${activeId === session.id ? "active" : ""}`} key={session.id}>
              <button className="session-main" onClick={() => onSelect(session.id)}>
                <span>{session.title}</span>
                <small>{formatSessionTime(session.updatedAt)}</small>
              </button>
              <button className="session-delete" onClick={() => onDelete(session)} aria-label={`删除${session.title}`}>
                <Trash2 size={15} />
              </button>
            </div>
          ))}
        </nav>
        <button className="settings-button" onClick={onSettings}><Settings size={18} />家长与学习设置</button>
      </aside>
    </>
  );
}

function Welcome({ onStarter }) {
  return (
    <section className="welcome">
      <div className="welcome-icon"><Sparkles size={30} /></div>
      <h1>今天想学点什么？</h1>
      <p>可以问知识、拍题目，也可以把不会的步骤告诉我。</p>
      <div className="starter-grid">
        {STARTERS.map(({ icon: Icon, title, text }) => (
          <button key={title} className="starter-card" onClick={() => onStarter(text)}>
            <Icon size={21} />
            <strong>{title}</strong>
            <span>{text}</span>
          </button>
        ))}
      </div>
      <div className="gentle-note">我也可能出错，重要答案记得和课本、老师一起核对。</div>
    </section>
  );
}

function Message({ message, isLastAssistant, onQuickAction }) {
  const isUser = message.role === "user";
  return (
    <article className={`message ${isUser ? "message-user" : "message-assistant"}`}>
      {!isUser && <div className="assistant-avatar"><Sparkles size={16} /></div>}
      <div className="message-column">
        {message.attachment && (
          <img className="message-image" src={message.attachment.preview || `/api/attachments/${message.attachment.id}`} alt="题目附件" />
        )}
        <div className="message-bubble">
          {isUser ? message.content : <MarkdownMessage>{message.content || (message.status === "streaming" ? "正在想一想…" : "")}</MarkdownMessage>}
          {message.status === "streaming" && message.content && <span className="typing-cursor" />}
          {message.status === "interrupted" && <span className="message-state">回答已停止</span>}
        </div>
        {!isUser && isLastAssistant && message.status === "completed" && (
          <div className="quick-actions">
            {QUICK_ACTIONS.map(({ label, icon: Icon, prompt }) => (
              <button key={label} onClick={() => onQuickAction(prompt)}><Icon size={15} />{label}</button>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

function Composer({ value, setValue, image, setImage, mode, setMode, loading, onSend, onStop, error, setError }) {
  const cameraRef = useRef(null);
  const galleryRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    const element = textareaRef.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 150)}px`;
  }, [value]);

  async function chooseImage(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      setError("");
      const dataUrl = await compressImage(file);
      setImage({ dataUrl, name: file.name });
    } catch (reason) {
      setError(reason.message);
    }
  }

  function keyDown(event) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      onSend();
    }
  }

  return (
    <div className="composer-wrap">
      {error && <div className="composer-error"><span>{error}</span><button onClick={() => setError("")}><X size={15} /></button></div>}
      <div className="composer">
        {image && (
          <div className="image-preview">
            <img src={image.dataUrl} alt="待发送题目" />
            <button onClick={() => setImage(null)} aria-label="移除图片"><X size={15} /></button>
          </div>
        )}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={keyDown}
          placeholder={image ? "可以补充：你希望我怎么帮你？" : "输入问题，或拍下一道题…"}
          rows="1"
          maxLength="10000"
          disabled={loading}
          aria-label="问题输入框"
        />
        <div className="composer-toolbar">
          <div className="composer-left">
            <input ref={cameraRef} className="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={chooseImage} />
            <input ref={galleryRef} className="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp" onChange={chooseImage} />
            <button className="tool-button" onClick={() => cameraRef.current?.click()} disabled={loading} title="打开相机拍题" aria-label="打开相机拍题">
              <Camera size={19} /><span>拍照</span>
            </button>
            <button className="tool-button" onClick={() => galleryRef.current?.click()} disabled={loading} title="从相册或文件中选择图片" aria-label="从相册或文件中选择图片">
              <ImagePlus size={19} /><span>相册</span>
            </button>
            <select value={mode} onChange={(event) => setMode(event.target.value)} disabled={loading} aria-label="学习模式">
              <option value="guide">引导模式</option>
              <option value="direct">直接讲解</option>
            </select>
          </div>
          {loading ? (
            <button className="send-button stop" onClick={onStop} title="停止生成"><CircleStop size={20} /></button>
          ) : (
            <button className="send-button" onClick={onSend} disabled={!value.trim() && !image} title="发送"><Send size={19} /></button>
          )}
        </div>
      </div>
      <p className="composer-hint">可拍照或从相册选择 · 每次 1 张图片 · Enter 发送</p>
    </div>
  );
}

function SettingsModal({ settings, models, onClose, onSaved, onClear }) {
  const [form, setForm] = useState(settings);
  const [currentPin, setCurrentPin] = useState("");
  const [newPin, setNewPin] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    setError("");
    try {
      const updated = await api("/api/settings", {
        method: "PUT",
        body: JSON.stringify({ ...form, currentPin, newPin }),
      });
      onSaved(updated);
    } catch (reason) {
      setError(reason.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="settings-title">
        <header><div><span className="eyebrow">家长设置</span><h2 id="settings-title">调整学习方式</h2></div><button className="icon-button" onClick={onClose}><X size={20} /></button></header>
        <label>学段<select value={form.gradeLevel} onChange={(e) => setForm({ ...form, gradeLevel: e.target.value })}><option value="primary">小学</option><option value="junior">初中</option><option value="senior">高中</option></select></label>
        <label>回答风格<select value={form.responseStyle} onChange={(e) => setForm({ ...form, responseStyle: e.target.value })}><option value="concise">简洁</option><option value="detailed">详细</option></select></label>
        <label>默认学习模式<select value={form.learningMode} onChange={(e) => setForm({ ...form, learningMode: e.target.value })}><option value="guide">先提示，再讲答案</option><option value="direct">直接分步骤讲解</option></select></label>
        <label>思考深度<select value={form.reasoningEffort} onChange={(e) => setForm({ ...form, reasoningEffort: e.target.value })}><option value="low">快速</option><option value="medium">标准（推荐）</option><option value="high">深入</option></select></label>
        <label>回答模型<select value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })}>{models.map((model) => <option value={model} key={model}>{model}</option>)}</select></label>
        {settings.pinSet && <label>当前家长 PIN<input type="password" inputMode="numeric" value={currentPin} onChange={(e) => setCurrentPin(e.target.value)} placeholder="修改或删除数据时需要" /></label>}
        <label>{settings.pinSet ? "设置新的 PIN（可不填）" : "设置家长 PIN（推荐）"}<input type="password" inputMode="numeric" value={newPin} onChange={(e) => setNewPin(e.target.value)} placeholder="4—8 位数字" /></label>
        {error && <p className="modal-error">{error}</p>}
        <div className="privacy-note">聊天和题目图片保存在这台电脑上。当前版本不会主动联网搜索。</div>
        <div className="modal-actions">
          <button className="danger-text" onClick={() => onClear(currentPin)}>清除全部记录</button>
          <div><button className="secondary" onClick={onClose}>取消</button><button className="primary" disabled={saving} onClick={save}>{saving ? "保存中…" : "保存设置"}</button></div>
        </div>
      </section>
    </div>
  );
}

export default function App() {
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [image, setImage] = useState(null);
  const [mode, setMode] = useState("guide");
  const [settings, setSettings] = useState({ gradeLevel: "junior", responseStyle: "concise", learningMode: "guide", reasoningEffort: "medium", model: "gpt-5.6-sol", pinSet: false });
  const [models, setModels] = useState(["gpt-5.6-sol"]);
  const [showSettings, setShowSettings] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [booting, setBooting] = useState(true);
  const [error, setError] = useState("");
  const [bridgeOnline, setBridgeOnline] = useState(true);
  const abortRef = useRef(null);
  const bottomRef = useRef(null);

  const lastAssistantIndex = useMemo(() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) if (messages[index].role === "assistant") return index;
    return -1;
  }, [messages]);

  useEffect(() => {
    Promise.all([api("/api/sessions"), api("/api/settings"), api("/api/health"), api("/api/models")])
      .then(([sessionData, settingData, health, modelData]) => {
        setSessions(sessionData);
        setSettings(settingData);
        setMode(settingData.learningMode);
        const availableModels = Array.isArray(modelData.models) ? modelData.models : [];
        setModels([...new Set([settingData.model, ...availableModels])]);
        setBridgeOnline(Boolean(health.bridge));
      })
      .catch((reason) => setError(reason.message))
      .finally(() => setBooting(false));
  }, []);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: loading ? "auto" : "smooth" }); }, [messages, loading]);

  async function refreshSessions() {
    const data = await api("/api/sessions");
    setSessions(data);
  }

  async function newChat() {
    if (loading) return;
    setActiveId(null);
    setMessages([]);
    setText("");
    setImage(null);
    setError("");
    setSidebarOpen(false);
  }

  async function selectSession(id) {
    if (loading) return;
    try {
      const session = await api(`/api/sessions/${id}`);
      setActiveId(id);
      setMessages(session.messages);
      setError("");
      setSidebarOpen(false);
    } catch (reason) {
      setError(reason.message);
    }
  }

  async function deleteSession(session) {
    if (!window.confirm(`删除“${session.title}”？删除后不能恢复。`)) return;
    const pin = settings.pinSet ? window.prompt("请输入家长 PIN：") : "";
    if (settings.pinSet && pin === null) return;
    try {
      await api(`/api/sessions/${session.id}`, { method: "DELETE", body: JSON.stringify({ pin }) });
      if (activeId === session.id) await newChat();
      await refreshSessions();
    } catch (reason) {
      setError(reason.message);
    }
  }

  async function clearAll(pin) {
    if (!window.confirm("确定清除全部聊天记录和题目图片？此操作不能恢复。")) return;
    try {
      await api("/api/data", { method: "DELETE", body: JSON.stringify({ pin }) });
      setShowSettings(false);
      await newChat();
      await refreshSessions();
    } catch (reason) {
      setError(reason.message);
    }
  }

  async function send(overrideText) {
    const outgoing = (overrideText ?? text).trim();
    if (loading || (!outgoing && !image)) return;
    setError("");
    setLoading(true);
    const outgoingImage = image;
    setText("");
    setImage(null);

    let sessionId = activeId;
    try {
      if (!sessionId) {
        const session = await api("/api/sessions", { method: "POST", body: "{}" });
        sessionId = session.id;
        setActiveId(sessionId);
      }
      const userMessage = {
        id: `local-user-${Date.now()}`,
        role: "user",
        content: outgoing || "请帮我识别并讲解这张题目图片。",
        status: "completed",
        attachment: outgoingImage ? { preview: outgoingImage.dataUrl } : null,
      };
      const assistantId = `local-assistant-${Date.now()}`;
      setMessages((current) => [...current, userMessage, { id: assistantId, role: "assistant", content: "", status: "streaming" }]);

      const controller = new AbortController();
      abortRef.current = controller;
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId, message: outgoing, imageDataUrl: outgoingImage?.dataUrl || null, mode }),
        signal: controller.signal,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.error || "发送失败，请稍后重试。 ");
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let doneEvent = false;
      while (true) {
        const { value, done } = await reader.read();
        const chunk = decoder.decode(value || new Uint8Array(), { stream: !done });
        const parsed = takeNdjsonLines(buffer, chunk);
        buffer = parsed.remainder;
        for (const event of parsed.events) {
          if (event.type === "delta") {
            setMessages((current) => current.map((item) => item.id === assistantId ? { ...item, content: item.content + event.text } : item));
          } else if (event.type === "done") {
            doneEvent = true;
            setMessages((current) => current.map((item) => item.id === assistantId ? { ...item, id: event.messageId, status: "completed" } : item));
          } else if (event.type === "error") {
            throw new Error(event.error);
          }
        }
        if (done) break;
      }
      if (!doneEvent) throw new Error("回答意外中断，请重试。 ");
      setBridgeOnline(true);
      await refreshSessions();
    } catch (reason) {
      if (reason.name === "AbortError") {
        setMessages((current) => current.map((item) => item.status === "streaming" ? { ...item, status: "interrupted" } : item));
      } else {
        setError(reason.message);
        setMessages((current) => current.filter((item) => item.status !== "streaming"));
        if (reason.message.includes("连接") || reason.message.includes("模型")) setBridgeOnline(false);
      }
      await refreshSessions().catch(() => {});
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }

  return (
    <div className="app-shell">
      <Sidebar open={sidebarOpen} sessions={sessions} activeId={activeId} onSelect={selectSession} onNew={newChat} onDelete={deleteSession} onSettings={() => setShowSettings(true)} onClose={() => setSidebarOpen(false)} />
      <main className="main-panel">
        <header className="topbar">
          <button className="icon-button menu-button" onClick={() => setSidebarOpen(true)}><Menu size={21} /></button>
          <div className="mobile-brand"><MessageCircleQuestion size={19} /><strong>小问号</strong></div>
          <div className={`service-status ${bridgeOnline ? "online" : "offline"}`}><span />{bridgeOnline ? "学习助手在线" : "模型暂时离线"}</div>
          <button className="new-mobile icon-button" onClick={newChat} title="新对话"><Plus size={21} /></button>
        </header>
        <div className="conversation">
          {booting ? (
            <div className="loading-screen"><div className="loading-dot" /><p>正在准备学习空间…</p></div>
          ) : messages.length === 0 ? (
            <Welcome onStarter={(starter) => setText(starter)} />
          ) : (
            <div className="messages">
              {messages.map((message, index) => (
                <Message key={message.id} message={message} isLastAssistant={index === lastAssistantIndex} onQuickAction={send} />
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>
        <Composer value={text} setValue={setText} image={image} setImage={setImage} mode={mode} setMode={setMode} loading={loading} onSend={() => send()} onStop={() => abortRef.current?.abort()} error={error} setError={setError} />
      </main>
      {showSettings && (
        <SettingsModal settings={settings} models={models} onClose={() => setShowSettings(false)} onSaved={(updated) => { setSettings(updated); setMode(updated.learningMode); setShowSettings(false); }} onClear={clearAll} />
      )}
    </div>
  );
}
