import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { BookCheck, Check, ChevronLeft, ChevronRight, CircleHelp, Library, LoaderCircle } from "lucide-react";
import { COURSE_LESSONS, COURSE_ROOT, COURSE_SECTIONS, cleanCourseMarkdown, parseCompletedLessons } from "./course.js";

function storageKey(profileId, suffix) {
  return `study-agent-course-${suffix}-${profileId || "default"}`;
}

function CourseMarkdown({ children }) {
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

export default function CourseLibrary({ profileId, onAskLesson }) {
  const initialLessonId = window.localStorage.getItem(storageKey(profileId, "last"));
  const [lessonId, setLessonId] = useState(
    COURSE_LESSONS.some((lesson) => lesson.id === initialLessonId) ? initialLessonId : COURSE_LESSONS[0].id,
  );
  const [markdown, setMarkdown] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [completed, setCompleted] = useState(() => (
    parseCompletedLessons(window.localStorage.getItem(storageKey(profileId, "completed")))
  ));

  const lessonIndex = COURSE_LESSONS.findIndex((lesson) => lesson.id === lessonId);
  const lesson = COURSE_LESSONS[lessonIndex] || COURSE_LESSONS[0];
  const previous = lessonIndex > 0 ? COURSE_LESSONS[lessonIndex - 1] : null;
  const next = lessonIndex < COURSE_LESSONS.length - 1 ? COURSE_LESSONS[lessonIndex + 1] : null;
  const isCompleted = completed.includes(lesson.id);
  const learningLessons = useMemo(() => COURSE_LESSONS.filter((item) => item.kind !== "reference"), []);
  const completedLearning = completed.filter((id) => learningLessons.some((lessonItem) => lessonItem.id === id)).length;
  const progress = Math.round((completedLearning / learningLessons.length) * 100);

  useEffect(() => {
    const savedLesson = window.localStorage.getItem(storageKey(profileId, "last"));
    const nextLesson = COURSE_LESSONS.some((item) => item.id === savedLesson) ? savedLesson : COURSE_LESSONS[0].id;
    setLessonId(nextLesson);
    setCompleted(parseCompletedLessons(window.localStorage.getItem(storageKey(profileId, "completed"))));
  }, [profileId]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setMarkdown("");
    fetch(`${COURSE_ROOT}/${lesson.file}`, { signal: controller.signal, credentials: "same-origin" })
      .then((response) => {
        if (!response.ok) throw new Error("课程内容暂时无法加载。");
        return response.text();
      })
      .then((content) => setMarkdown(cleanCourseMarkdown(content)))
      .catch((reason) => {
        if (reason.name !== "AbortError") setError(reason.message || "课程内容暂时无法加载。");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    window.localStorage.setItem(storageKey(profileId, "last"), lesson.id);
    return () => controller.abort();
  }, [lesson.file, lesson.id, profileId, reloadKey]);

  function selectLesson(id) {
    setLessonId(id);
    document.querySelector(".course-reader")?.scrollTo({ top: 0, behavior: "smooth" });
  }

  function toggleCompleted() {
    const updated = isCompleted ? completed.filter((id) => id !== lesson.id) : [...completed, lesson.id];
    setCompleted(updated);
    window.localStorage.setItem(storageKey(profileId, "completed"), JSON.stringify(updated));
  }

  return (
    <section className="course-center" aria-label="系统课程">
      <aside className="course-outline">
        <div className="course-outline-heading">
          <div className="course-icon"><Library size={21} /></div>
          <div><span>系统课程</span><strong>从零开始学信奥</strong></div>
        </div>
        <div className="course-progress" aria-label={`学习进度 ${progress}%`}>
          <div><span>第一部分进度</span><strong>{completedLearning}/{learningLessons.length}</strong></div>
          <div className="course-progress-track"><i style={{ width: `${progress}%` }} /></div>
        </div>
        <label className="course-mobile-picker">
          <span>选择章节</span>
          <select value={lesson.id} onChange={(event) => selectLesson(event.target.value)}>
            {COURSE_LESSONS.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
          </select>
        </label>
        <nav className="course-outline-list" aria-label="课程目录">
          {COURSE_SECTIONS.map((section) => (
            <div className="course-outline-section" key={section.label}>
              <span>{section.label}</span>
              {section.lessons.map((item) => (
                <button className={item.id === lesson.id ? "active" : ""} key={item.id} onClick={() => selectLesson(item.id)}>
                  <i className={completed.includes(item.id) ? "done" : ""}>{completed.includes(item.id) ? <Check size={13} /> : null}</i>
                  <span>{item.shortTitle}<small>{item.duration}</small></span>
                </button>
              ))}
            </div>
          ))}
        </nav>
      </aside>

      <div className="course-reader">
        <div className="course-reader-bar">
          <div><span>第一部分 · 走进 C++ 与信息学竞赛</span><strong>{lesson.shortTitle}</strong></div>
          <button className="course-ask-button" onClick={() => onAskLesson(lesson.title)}><CircleHelp size={16} />就本节提问</button>
        </div>

        <article className="course-paper">
          {loading ? (
            <div className="course-state"><LoaderCircle className="course-spinner" size={25} /><span>正在打开课程…</span></div>
          ) : error ? (
            <div className="course-state error"><span>{error}</span><button onClick={() => setReloadKey((value) => value + 1)}>重新加载</button></div>
          ) : (
            <div className="course-markdown"><CourseMarkdown>{markdown}</CourseMarkdown></div>
          )}
        </article>

        <footer className="course-footer">
          <button className="course-page-button" disabled={!previous} onClick={() => previous && selectLesson(previous.id)}>
            <ChevronLeft size={17} /><span>{previous ? previous.shortTitle : "已经是第一节"}</span>
          </button>
          <button className={`course-complete-button ${isCompleted ? "completed" : ""}`} onClick={toggleCompleted}>
            {isCompleted ? <Check size={17} /> : <BookCheck size={17} />}{isCompleted ? "已完成本节" : "标记为已完成"}
          </button>
          <button className="course-page-button next" disabled={!next} onClick={() => next && selectLesson(next.id)}>
            <span>{next ? next.shortTitle : "已经全部读完"}</span><ChevronRight size={17} />
          </button>
        </footer>
      </div>
    </section>
  );
}
