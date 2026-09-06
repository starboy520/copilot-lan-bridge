export const COURSE_ROOT = "/curriculum/noip-from-zero/docs";

export const COURSE_SECTIONS = [
  {
    label: "第一部分 · 入门基础",
    partTitle: "第一部分 · 走进 C++ 与信息学竞赛",
    lessons: [
      { id: "overview", title: "导读与学习地图", shortTitle: "学习导读", file: "part-01/00-overview.md", duration: "20 分钟" },
      { id: "chapter-1", title: "第 1 章：简单程序与 OI", shortTitle: "简单程序与 OI", file: "part-01/01-simple-programs-and-oi.md", duration: "2～3 课时" },
      { id: "chapter-2", title: "第 2 章：基础数据类型", shortTitle: "基础数据类型", file: "part-01/02-basic-data-types.md", duration: "2～3 课时" },
      { id: "chapter-3", title: "第 3 章：格式化输入和输出", shortTitle: "格式化输入和输出", file: "part-01/03-formatted-input-output.md", duration: "2 课时" },
      { id: "chapter-4", title: "第 4 章：计数器与累加器", shortTitle: "计数器与累加器", file: "part-01/04-counters-and-accumulators.md", duration: "2 课时" },
      { id: "chapter-5", title: "第 5 章：整数与取余", shortTitle: "整数与取余", file: "part-01/05-integers-and-modulo.md", duration: "2～3 课时" },
    ],
  },
  {
    label: "第一部分 · 巩固复习",
    partTitle: "第一部分 · 走进 C++ 与信息学竞赛",
    lessons: [
      { id: "project", title: "综合项目：学习积分结算器", shortTitle: "综合项目", file: "part-01/06-project-learning-points.md", duration: "1～2 课时" },
      { id: "review", title: "第一部分复习清单", shortTitle: "复习清单", file: "part-01/07-review-checklist.md", duration: "30 分钟" },
      { id: "answers", title: "第一部分练习答案与提示", shortTitle: "练习答案", file: "part-01/08-exercise-answers.md", duration: "按需查看", kind: "reference" },
    ],
  },
  {
    label: "第二部分 · 选择结构",
    partTitle: "第二部分 · 让程序学会做选择",
    lessons: [
      { id: "part-2-overview", title: "选择结构导读与学习地图", shortTitle: "学习导读", file: "part-02/00-overview.md", duration: "20 分钟" },
      { id: "part-2-chapter-1", title: "第 1 章：条件与比较运算", shortTitle: "条件与比较", file: "part-02/01-comparisons-and-conditions.md", duration: "2 课时" },
      { id: "part-2-chapter-2", title: "第 2 章：单分支 if", shortTitle: "单分支 if", file: "part-02/02-single-if.md", duration: "2 课时" },
      { id: "part-2-chapter-3", title: "第 3 章：双分支 if...else", shortTitle: "双分支", file: "part-02/03-if-else.md", duration: "2 课时" },
      { id: "part-2-chapter-4", title: "第 4 章：多分支", shortTitle: "多分支", file: "part-02/04-multiple-branches.md", duration: "2 课时" },
      { id: "part-2-chapter-5", title: "第 5 章：组合条件与逻辑运算", shortTitle: "组合条件", file: "part-02/05-logical-operators.md", duration: "2 课时" },
      { id: "part-2-chapter-6", title: "第 6 章：浅层嵌套与边界测试", shortTitle: "嵌套与边界", file: "part-02/06-nesting-and-boundaries.md", duration: "2 课时" },
    ],
  },
  {
    label: "第二部分 · 巩固复习",
    partTitle: "第二部分 · 让程序学会做选择",
    lessons: [
      { id: "part-2-project", title: "综合项目：信奥闯关判定器", shortTitle: "综合项目", file: "part-02/07-project-challenge-judge.md", duration: "1～2 课时" },
      { id: "part-2-review", title: "第二部分复习清单", shortTitle: "复习清单", file: "part-02/08-review-checklist.md", duration: "30 分钟" },
      { id: "part-2-answers", title: "第二部分练习答案与提示", shortTitle: "练习答案", file: "part-02/09-exercise-answers.md", duration: "按需查看", kind: "reference" },
    ],
  },
  {
    label: "陪学资料",
    partTitle: "家长与教师资料",
    lessons: [
      { id: "teaching-guide", title: "第一部分给家长或老师的使用建议", shortTitle: "第一部分陪学", file: "part-01/09-teaching-guide.md", duration: "家长阅读", kind: "reference" },
      { id: "part-2-teaching-guide", title: "第二部分给家长或老师的使用建议", shortTitle: "第二部分陪学", file: "part-02/10-teaching-guide.md", duration: "家长阅读", kind: "reference" },
    ],
  },
];

export const COURSE_LESSONS = COURSE_SECTIONS.flatMap((section) => (
  section.lessons.map((lesson) => ({ ...lesson, partTitle: section.partTitle }))
));

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
