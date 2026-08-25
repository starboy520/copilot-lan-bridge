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
  ImagePlus,
  Lightbulb,
  LockKeyhole,
  LogOut,
  Menu,
  MessageCircleQuestion,
  Pencil,
  Plus,
  RotateCcw,
  Send,
  Settings,
  Sparkles,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
import { takeNdjsonLines } from "./stream.js";

const LEARNING_ACTIONS = [
  { label: "再提示一点", icon: Lightbulb, prompt: "请在刚才提示的基础上再给一个更具体的提示，但先不要公布最终答案。" },
  { label: "分步骤讲解", icon: BookOpen, prompt: "请分步骤讲解这道题的完整关键过程，最后一步可以先留给我完成。" },
  { label: "查看完整答案", icon: Check, prompt: "请给出这道题的完整过程、最终答案和一个简短的检查方法。" },
  { label: "再练一道", icon: RotateCcw, prompt: "请围绕刚才的知识点出一道难度相近的题，暂时不要给答案，等我作答。" },
];

const REVIEW_ACTIONS = [
  { label: "给订正提示", icon: Lightbulb, prompt: "请只针对第一道错题再给一个具体的订正提示，先不要给完整答案。" },
  { label: "看完整订正", icon: BookOpen, prompt: "请给出这些错题的完整订正过程，并说明每题如何检查。" },
  { label: "总结错因", icon: Check, prompt: "请把这次作业的主要错因归纳成不超过 3 点，并告诉我下次如何避免。" },
  { label: "出一道巩固题", icon: RotateCcw, prompt: "请根据这次最主要的错因出一道巩固题，暂时不要给答案。" },
];

const STARTERS = [
  { icon: Lightbulb, title: "问知识", text: "帮我理解质数，不要只背定义", mode: "guide" },
  { icon: Camera, title: "拍题学习", text: "拍下题目，我会先确认题意，再从提示开始", mode: "guide" },
  { icon: Check, title: "批改作业", text: "上传做好的作业，逐题检查并帮我订正", mode: "review" },
];

const normalizeMode = (value) => value === "review" ? "review" : "guide";

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/api/auth/")) {
      window.dispatchEvent(new Event("study-agent-auth-required"));
    }
    const error = new Error(data.error || "请求失败，请稍后重试。 ");
    error.status = response.status;
    throw error;
  }
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

function AccessScreen({ mode, onAuthenticated }) {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const setup = mode === "setup";

  async function submit(event) {
    event.preventDefault();
    if (setup && password !== confirmPassword) {
      setError("两次输入的密码不一致。");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await api(setup ? "/api/auth/setup" : "/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      onAuthenticated();
    } catch (reason) {
      if (setup && reason.status === 409) {
        window.location.reload();
        return;
      }
      setError(reason.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="access-screen">
      <form className="access-card" onSubmit={submit}>
        <div className="access-mark"><LockKeyhole size={29} /></div>
        <span className="eyebrow">家庭学习空间</span>
        <h1>{setup ? "设置家庭密码" : "欢迎回来"}</h1>
        <p>{setup ? "首次使用时设置，全家设备使用同一个密码进入。" : "请输入家庭密码，进入孩子的学习空间。"}</p>
        <label>家庭密码<input autoFocus type="password" autoComplete={setup ? "new-password" : "current-password"} minLength="8" maxLength="64" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="8—64 个字符" /></label>
        {setup && <label>再输入一次<input type="password" autoComplete="new-password" minLength="8" maxLength="64" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} /></label>}
        {error && <p className="access-error">{error}</p>}
        <button className="primary access-submit" disabled={submitting || password.length < 8 || (setup && confirmPassword.length < 8)} type="submit">{submitting ? "请稍候…" : setup ? "设置并进入" : "进入学习空间"}</button>
        <small>连续输错 5 次会暂时锁定。请不要将服务端口直接暴露到公网。</small>
      </form>
    </main>
  );
}

function Sidebar({ open, profiles, activeProfileId, sessions, activeId, onProfileChange, onManageProfiles, onSelect, onNew, onDelete, onSettings, onLogout, onClose }) {
  return (
    <>
      {open && <button className="sidebar-backdrop" aria-label="关闭会话列表" onClick={onClose} />}
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <div className="brand-row">
          <div className="brand-mark"><MessageCircleQuestion size={22} /></div>
          <div><strong>小问号</strong><span>学习助手</span></div>
          <button className="icon-button sidebar-close" onClick={onClose} aria-label="关闭"><X size={20} /></button>
        </div>
        <div className="profile-picker">
          <label htmlFor="profile-select">当前孩子</label>
          <div>
            <select id="profile-select" value={activeProfileId || ""} onChange={(event) => onProfileChange(event.target.value)}>
              {profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
            </select>
            <button className="icon-button" onClick={onManageProfiles} title="管理孩子档案" aria-label="管理孩子档案"><UserRound size={18} /></button>
          </div>
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
        <div className="sidebar-actions">
          <button className="settings-button" onClick={onSettings}><Settings size={18} />家长与学习设置</button>
          <button className="logout-button" onClick={onLogout} title="退出登录" aria-label="退出登录"><LogOut size={17} /></button>
        </div>
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
        {STARTERS.map(({ icon: Icon, title, text, mode }) => (
          <button key={title} className="starter-card" onClick={() => onStarter({ text, mode })}>
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

function ThinkingIndicator({ imageReview, progressText }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  if (!imageReview) return <p>{progressText || "正在想一想…"}</p>;
  let message = progressText || "图片已收到，正在识别题目和作答…";
  if (elapsed >= 15) message = "正在逐题核对答案和解题步骤…";
  if (elapsed >= 45) message = "图片内容较多，仍在认真批改，请稍候…";
  return (
    <div className="review-progress">
      <span>{message}</span>
      <small>已等待 {elapsed} 秒，图片批改通常需要 30–90 秒</small>
    </div>
  );
}

function Message({ message, isLastAssistant, onQuickAction, mode }) {
  const isUser = message.role === "user";
  const quickActions = mode === "review" ? REVIEW_ACTIONS : LEARNING_ACTIONS;
  return (
    <article className={`message ${isUser ? "message-user" : "message-assistant"}`}>
      {!isUser && <div className="assistant-avatar"><Sparkles size={16} /></div>}
      <div className="message-column">
        {message.attachment && (
          <img className="message-image" src={message.attachment.preview || `/api/attachments/${message.attachment.id}`} alt="题目附件" />
        )}
        <div className="message-bubble">
          {isUser ? message.content : message.content ? (
            <MarkdownMessage>{message.content}</MarkdownMessage>
          ) : message.status === "streaming" ? (
            <ThinkingIndicator imageReview={message.imageReview} progressText={message.progressText} />
          ) : null}
          {message.status === "streaming" && message.content && <span className="typing-cursor" />}
          {message.status === "interrupted" && <span className="message-state">回答已停止</span>}
        </div>
        {!isUser && isLastAssistant && message.status === "completed" && (
          <div className="quick-actions">
            {quickActions.map(({ label, icon: Icon, prompt }) => (
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
          placeholder={image ? (mode === "review" ? "可补充批改要求，不填也可以直接发送…" : "可以补充：你希望我怎么帮你？") : (mode === "review" ? "上传作业图片，或粘贴需要批改的作答…" : "输入问题，或拍下一道题…")}
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
            <div className="task-switch" role="group" aria-label="学习任务">
              <button className={mode !== "review" ? "active" : ""} onClick={() => setMode("guide")} disabled={loading} type="button"><BookOpen size={16} />学习</button>
              <button className={mode === "review" ? "active" : ""} onClick={() => setMode("review")} disabled={loading} type="button"><Check size={16} />批改作业</button>
            </div>
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

function ProfileModal({ profiles, activeProfileId, onClose, onCreated, onRenamed, onDeleted }) {
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function createProfile() {
    setSaving(true);
    setError("");
    try {
      const profile = await api("/api/profiles", { method: "POST", body: JSON.stringify({ name }) });
      setName("");
      await onCreated(profile);
    } catch (reason) {
      setError(reason.message);
    } finally {
      setSaving(false);
    }
  }

  async function renameProfile(profile) {
    const nextName = window.prompt("请输入新的档案名称：", profile.name)?.trim();
    if (!nextName || nextName === profile.name) return;
    setError("");
    try {
      const updated = await api(`/api/profiles/${profile.id}`, { method: "PUT", body: JSON.stringify({ name: nextName }) });
      onRenamed(updated);
    } catch (reason) {
      setError(reason.message);
    }
  }

  async function deleteProfile(profile) {
    if (!window.confirm(`删除“${profile.name}”档案及其全部聊天和图片？此操作不能恢复。`)) return;
    setError("");
    try {
      await api(`/api/profiles/${profile.id}`, { method: "DELETE", body: "{}" });
      await onDeleted(profile.id);
    } catch (reason) {
      setError(reason.message);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="profiles-title">
        <header><div><span className="eyebrow">家庭学习</span><h2 id="profiles-title">孩子档案</h2></div><button className="icon-button" onClick={onClose}><X size={20} /></button></header>
        <div className="profile-list">
          {profiles.map((profile) => (
            <div className={`profile-list-row ${profile.id === activeProfileId ? "active" : ""}`} key={profile.id}>
              <div><strong>{profile.name}</strong><span>{profile.sessionCount} 个对话{profile.id === activeProfileId ? " · 当前" : ""}</span></div>
              <div>
                <button className="icon-button" onClick={() => renameProfile(profile)} aria-label={`重命名${profile.name}`}><Pencil size={16} /></button>
                <button className="icon-button danger-icon" disabled={profiles.length <= 1} onClick={() => deleteProfile(profile)} aria-label={`删除${profile.name}`}><Trash2 size={16} /></button>
              </div>
            </div>
          ))}
        </div>
        <label>新增孩子<input value={name} maxLength="20" onChange={(event) => setName(event.target.value)} placeholder="名字或昵称" /></label>
        {error && <p className="modal-error">{error}</p>}
        <div className="privacy-note">每个孩子拥有独立的聊天记录和学习设置，家庭密码统一保护整个学习空间。</div>
        <div className="modal-actions profile-actions"><button className="secondary" onClick={onClose}>完成</button><button className="primary" disabled={saving || !name.trim() || profiles.length >= 8} onClick={createProfile}>{saving ? "创建中…" : "新增档案"}</button></div>
      </section>
    </div>
  );
}

function SettingsModal({ profile, settings, models, onClose, onSaved, onClear }) {
  const [form, setForm] = useState({ ...settings, learningMode: normalizeMode(settings.learningMode) });
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordSaved, setPasswordSaved] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [resettingPassword, setResettingPassword] = useState(false);

  async function save() {
    setSaving(true);
    setError("");
    try {
      const updated = await api("/api/settings", {
        method: "PUT",
        body: JSON.stringify({ ...form, profileId: profile.id }),
      });
      onSaved(updated);
    } catch (reason) {
      setError(reason.message);
    } finally {
      setSaving(false);
    }
  }

  async function resetFamilyPassword() {
    setError("");
    setPasswordSaved(false);
    if (newPassword !== confirmPassword) {
      setError("两次输入的家庭密码不一致。");
      return;
    }
    setResettingPassword(true);
    try {
      await api("/api/auth/password", {
        method: "PUT",
        body: JSON.stringify({ newPassword }),
      });
      setNewPassword("");
      setConfirmPassword("");
      setPasswordSaved(true);
    } catch (reason) {
      setError(reason.message);
    } finally {
      setResettingPassword(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="settings-title">
        <header><div><span className="eyebrow">{profile.name}的设置</span><h2 id="settings-title">调整学习方式</h2></div><button className="icon-button" onClick={onClose}><X size={20} /></button></header>
        <label>学段<select value={form.gradeLevel} onChange={(e) => setForm({ ...form, gradeLevel: e.target.value })}><option value="primary">小学</option><option value="junior">初中</option><option value="senior">高中</option></select></label>
        <label>回答风格<select value={form.responseStyle} onChange={(e) => setForm({ ...form, responseStyle: e.target.value })}><option value="concise">简洁</option><option value="detailed">详细</option></select></label>
        <div className="setting-note"><strong>默认学习方式</strong><span>先提示，再按孩子需要逐步讲解；批改作业可在输入框旁一键切换。</span></div>
        <label>思考深度<select value={form.reasoningEffort} onChange={(e) => setForm({ ...form, reasoningEffort: e.target.value })}><option value="low">快速</option><option value="medium">标准（推荐）</option><option value="high">深入</option></select></label>
        <label>回答模型<select value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })}>{models.map((model) => <option value={model} key={model}>{model}</option>)}</select></label>
        <section className="password-reset-section">
          <h3>重置家庭密码</h3>
          <p>输入两次新密码即可重置。当前设备保持登录，其他设备需要使用新密码重新进入。</p>
          <label>新的家庭密码<input type="password" autoComplete="new-password" minLength="8" maxLength="64" value={newPassword} onChange={(e) => { setNewPassword(e.target.value); setPasswordSaved(false); }} placeholder="8—64 个字符" /></label>
          <label>再输入一次<input type="password" autoComplete="new-password" minLength="8" maxLength="64" value={confirmPassword} onChange={(e) => { setConfirmPassword(e.target.value); setPasswordSaved(false); }} /></label>
          <button className="secondary password-reset-button" disabled={resettingPassword || newPassword.length < 8 || confirmPassword.length < 8} onClick={resetFamilyPassword}>{resettingPassword ? "正在重置…" : "重置家庭密码"}</button>
          {passwordSaved && <p className="modal-success">家庭密码已重置。</p>}
        </section>
        {error && <p className="modal-error">{error}</p>}
        <div className="privacy-note">聊天和题目图片保存在这台电脑上。当前版本不会主动联网搜索。</div>
        <div className="modal-actions">
          <button className="danger-text" onClick={onClear}>清除{profile.name}的记录</button>
          <div><button className="secondary" onClick={onClose}>取消</button><button className="primary" disabled={saving} onClick={save}>{saving ? "保存中…" : "保存设置"}</button></div>
        </div>
      </section>
    </div>
  );
}

export default function App() {
  const [authState, setAuthState] = useState("checking");
  const [authError, setAuthError] = useState("");
  const [profiles, setProfiles] = useState([]);
  const [activeProfileId, setActiveProfileId] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [image, setImage] = useState(null);
  const [mode, setMode] = useState("guide");
  const [settings, setSettings] = useState({ gradeLevel: "junior", responseStyle: "concise", learningMode: "guide", reasoningEffort: "medium", model: "gpt-5.6-sol" });
  const [models, setModels] = useState(["gpt-5.6-sol"]);
  const [showSettings, setShowSettings] = useState(false);
  const [showProfiles, setShowProfiles] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [booting, setBooting] = useState(true);
  const [error, setError] = useState("");
  const [bridgeOnline, setBridgeOnline] = useState(true);
  const abortRef = useRef(null);
  const bottomRef = useRef(null);
  const activeProfile = profiles.find((profile) => profile.id === activeProfileId) || profiles[0] || null;

  const lastAssistantIndex = useMemo(() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) if (messages[index].role === "assistant") return index;
    return -1;
  }, [messages]);

  useEffect(() => {
    api("/api/auth/status")
      .then((status) => setAuthState(status.authenticated ? "authenticated" : status.configured ? "login" : "setup"))
      .catch((reason) => { setAuthError(reason.message); setAuthState("error"); });
  }, []);

  useEffect(() => {
    const requireLogin = () => {
      abortRef.current?.abort();
      setAuthState("login");
      setProfiles([]);
      setSessions([]);
      setMessages([]);
      setActiveId(null);
    };
    window.addEventListener("study-agent-auth-required", requireLogin);
    return () => window.removeEventListener("study-agent-auth-required", requireLogin);
  }, []);

  useEffect(() => {
    if (authState !== "authenticated") return;
    setBooting(true);
    setError("");
    Promise.all([api("/api/profiles"), api("/api/health"), api("/api/models")])
      .then(async ([profileData, health, modelData]) => {
        const savedId = window.localStorage.getItem("study-agent-profile-id");
        const selected = profileData.find((profile) => profile.id === savedId) || profileData[0];
        if (!selected) throw new Error("没有可用的孩子档案。");
        const [sessionData, settingData] = await Promise.all([
          api(`/api/sessions?profileId=${encodeURIComponent(selected.id)}`),
          api(`/api/settings?profileId=${encodeURIComponent(selected.id)}`),
        ]);
        setProfiles(profileData);
        setActiveProfileId(selected.id);
        setSessions(sessionData);
        setSettings(settingData);
        setMode(normalizeMode(settingData.learningMode));
        const availableModels = Array.isArray(modelData.models) ? modelData.models : [];
        setModels([...new Set([settingData.model, ...availableModels])]);
        setBridgeOnline(Boolean(health.bridge));
      })
      .catch((reason) => setError(reason.message))
      .finally(() => setBooting(false));
  }, [authState]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: loading ? "auto" : "smooth" }); }, [messages, loading]);

  async function refreshSessions() {
    if (!activeProfileId) return;
    const data = await api(`/api/sessions?profileId=${encodeURIComponent(activeProfileId)}`);
    setSessions(data);
    setProfiles((current) => current.map((profile) => (
      profile.id === activeProfileId ? { ...profile, sessionCount: data.length } : profile
    )));
  }

  async function loadProfile(profileId) {
    if (loading || profileId === activeProfileId) return;
    setError("");
    const [sessionData, settingData] = await Promise.all([
      api(`/api/sessions?profileId=${encodeURIComponent(profileId)}`),
      api(`/api/settings?profileId=${encodeURIComponent(profileId)}`),
    ]);
    window.localStorage.setItem("study-agent-profile-id", profileId);
    setActiveProfileId(profileId);
    setSessions(sessionData);
    setSettings(settingData);
    setMode(normalizeMode(settingData.learningMode));
    setActiveId(null);
    setMessages([]);
    setText("");
    setImage(null);
    setSidebarOpen(false);
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
    try {
      await api(`/api/sessions/${session.id}`, { method: "DELETE", body: "{}" });
      if (activeId === session.id) await newChat();
      await refreshSessions();
    } catch (reason) {
      setError(reason.message);
    }
  }

  async function clearAll() {
    if (!window.confirm(`确定清除${activeProfile?.name || "当前档案"}的全部聊天记录和题目图片？此操作不能恢复。`)) return;
    try {
      await api("/api/data", { method: "DELETE", body: JSON.stringify({ profileId: activeProfileId }) });
      setShowSettings(false);
      await newChat();
      await refreshSessions();
    } catch (reason) {
      setError(reason.message);
    }
  }

  async function logout() {
    if (loading) abortRef.current?.abort();
    await api("/api/auth/logout", { method: "POST", body: "{}" }).catch(() => {});
    setAuthState("login");
    setSidebarOpen(false);
    setProfiles([]);
    setSessions([]);
    setMessages([]);
    setActiveId(null);
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
        const session = await api("/api/sessions", { method: "POST", body: JSON.stringify({ profileId: activeProfileId }) });
        sessionId = session.id;
        setActiveId(sessionId);
      }
      const userMessage = {
        id: `local-user-${Date.now()}`,
        role: "user",
        content: outgoing || (mode === "review" ? "请逐题识别并批改这张作业图片。" : "请帮我识别并讲解这张题目图片。"),
        status: "completed",
        attachment: outgoingImage ? { preview: outgoingImage.dataUrl } : null,
      };
      const assistantId = `local-assistant-${Date.now()}`;
      setMessages((current) => [...current, userMessage, {
        id: assistantId,
        role: "assistant",
        content: "",
        status: "streaming",
        imageReview: Boolean(outgoingImage) && mode === "review",
        progressText: "",
      }]);

      const controller = new AbortController();
      abortRef.current = controller;
      const response = await fetch("/api/chat", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId, message: outgoing, imageDataUrl: outgoingImage?.dataUrl || null, mode }),
        signal: controller.signal,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        if (response.status === 401) window.dispatchEvent(new Event("study-agent-auth-required"));
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
          } else if (event.type === "status") {
            setMessages((current) => current.map((item) => item.id === assistantId ? { ...item, progressText: event.message || item.progressText } : item));
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

  if (authState === "checking") {
    return <div className="loading-screen full-screen"><div className="loading-dot" /><p>正在检查家庭准入…</p></div>;
  }
  if (authState === "setup" || authState === "login") {
    return <AccessScreen mode={authState} onAuthenticated={() => setAuthState("authenticated")} />;
  }
  if (authState === "error") {
    return <div className="loading-screen full-screen"><p>{authError || "无法连接学习助手。"}</p><button className="secondary" onClick={() => window.location.reload()}>重新加载</button></div>;
  }

  return (
    <div className="app-shell">
      <Sidebar open={sidebarOpen} profiles={profiles} activeProfileId={activeProfileId} sessions={sessions} activeId={activeId} onProfileChange={(id) => loadProfile(id).catch((reason) => setError(reason.message))} onManageProfiles={() => setShowProfiles(true)} onSelect={selectSession} onNew={newChat} onDelete={deleteSession} onSettings={() => setShowSettings(true)} onLogout={logout} onClose={() => setSidebarOpen(false)} />
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
            <Welcome onStarter={({ text: starterText, mode: starterMode }) => { setMode(starterMode); setText(starterText); }} />
          ) : (
            <div className="messages">
              {messages.map((message, index) => (
                <Message key={message.id} message={message} isLastAssistant={index === lastAssistantIndex} onQuickAction={send} mode={mode} />
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>
        <Composer value={text} setValue={setText} image={image} setImage={setImage} mode={mode} setMode={setMode} loading={loading} onSend={() => send()} onStop={() => abortRef.current?.abort()} error={error} setError={setError} />
      </main>
      {showSettings && (
        <SettingsModal profile={activeProfile} settings={settings} models={models} onClose={() => setShowSettings(false)} onSaved={(updated) => { setSettings(updated); setMode(normalizeMode(updated.learningMode)); setShowSettings(false); }} onClear={clearAll} />
      )}
      {showProfiles && (
        <ProfileModal
          profiles={profiles}
          activeProfileId={activeProfileId}
          onClose={() => setShowProfiles(false)}
          onCreated={async (profile) => { setProfiles((current) => [...current, profile]); await loadProfile(profile.id); }}
          onRenamed={(updated) => setProfiles((current) => current.map((profile) => profile.id === updated.id ? updated : profile))}
          onDeleted={async (profileId) => {
            const remaining = profiles.filter((profile) => profile.id !== profileId);
            setProfiles(remaining);
            if (profileId === activeProfileId) await loadProfile(remaining[0].id);
          }}
        />
      )}
    </div>
  );
}
