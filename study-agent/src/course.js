export const COURSE_ROOT = "/curriculum/noip-from-zero/docs/part-01";

export const COURSE_SECTIONS = [
  {
    label: "开始学习",
    lessons: [
      { id: "overview", title: "导读与学习地图", shortTitle: "学习导读", file: "00-overview.md", duration: "20 分钟" },
      { id: "chapter-1", title: "第 1 章：简单程序与 OI", shortTitle: "简单程序与 OI", file: "01-simple-programs-and-oi.md", duration: "2～3 课时" },
      { id: "chapter-2", title: "第 2 章：基础数据类型", shortTitle: "基础数据类型", file: "02-basic-data-types.md", duration: "2～3 课时" },
      { id: "chapter-3", title: "第 3 章：格式化输入和输出", shortTitle: "格式化输入和输出", file: "03-formatted-input-output.md", duration: "2 课时" },
      { id: "chapter-4", title: "第 4 章：计数器与累加器", shortTitle: "计数器与累加器", file: "04-counters-and-accumulators.md", duration: "2 课时" },
      { id: "chapter-5", title: "第 5 章：整数与取余", shortTitle: "整数与取余", file: "05-integers-and-modulo.md", duration: "2～3 课时" },
    ],
  },
  {
    label: "巩固与复习",
    lessons: [
      { id: "project", title: "综合项目：学习积分结算器", shortTitle: "综合项目", file: "06-project-learning-points.md", duration: "1～2 课时" },
      { id: "review", title: "第一部分复习清单", shortTitle: "复习清单", file: "07-review-checklist.md", duration: "30 分钟" },
      { id: "answers", title: "练习答案与提示", shortTitle: "练习答案", file: "08-exercise-answers.md", duration: "按需查看", kind: "reference" },
    ],
  },
  {
    label: "陪学资料",
    lessons: [
      { id: "teaching-guide", title: "给家长或老师的使用建议", shortTitle: "陪学建议", file: "09-teaching-guide.md", duration: "家长阅读", kind: "reference" },
    ],
  },
];

export const COURSE_LESSONS = COURSE_SECTIONS.flatMap((section) => section.lessons);

export function cleanCourseMarkdown(source) {
  const lines = String(source || "").replace(/\r\n/g, "\n").split("\n");
  const headingIndex = lines.findIndex((line) => /^#\s/.test(line));
  const content = headingIndex >= 0 ? lines.slice(headingIndex) : lines;

  while (content.length && !content.at(-1).trim()) content.pop();
  if (content.length && /^\[.+\]\(.+\)(?:\s*·\s*\[.+\]\(.+\))*$/.test(content.at(-1).trim())) {
    content.pop();
    while (content.length && !content.at(-1).trim()) content.pop();
    if (content.at(-1)?.trim() === "---") content.pop();
  }
  return content.join("\n").trim();
}

export function parseCompletedLessons(value) {
  try {
    const parsed = JSON.parse(value || "[]");
    return Array.isArray(parsed) ? parsed.filter((id) => COURSE_LESSONS.some((lesson) => lesson.id === id)) : [];
  } catch {
    return [];
  }
}
