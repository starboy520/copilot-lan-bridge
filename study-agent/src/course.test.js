import { describe, expect, it } from "vitest";
import { COURSE_LESSONS, COURSE_ROOT, COURSE_SECTIONS, cleanCourseMarkdown, parseCompletedLessons } from "./course.js";

describe("course helpers", () => {
  it("removes repository navigation around lesson markdown", () => {
    const source = "[目录](./README.md) · [下一章](./02.md)\n\n---\n\n# 第一章\n\n正文\n\n---\n\n[上一章](./00.md) · [目录](./README.md)";
    expect(cleanCourseMarkdown(source)).toBe("# 第一章\n\n正文");
  });

  it("keeps only known completed lesson ids", () => {
    expect(parseCompletedLessons(JSON.stringify([COURSE_LESSONS[0].id, "unknown"]))).toEqual([COURSE_LESSONS[0].id]);
    expect(parseCompletedLessons("not-json")).toEqual([]);
  });

  it("registers both course parts with unique ids and valid relative paths", () => {
    const ids = COURSE_LESSONS.map((lesson) => lesson.id);
    expect(COURSE_ROOT).toBe("/curriculum/noip-from-zero/docs");
    expect(COURSE_SECTIONS.some((section) => section.label.startsWith("第一部分"))).toBe(true);
    expect(COURSE_SECTIONS.some((section) => section.label.startsWith("第二部分"))).toBe(true);
    expect(new Set(ids).size).toBe(ids.length);
    expect(COURSE_LESSONS).toHaveLength(21);
    expect(COURSE_LESSONS.every((lesson) => /^part-0[12]\//.test(lesson.file))).toBe(true);
  });
});
