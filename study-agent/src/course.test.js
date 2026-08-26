import { describe, expect, it } from "vitest";
import { COURSE_LESSONS, cleanCourseMarkdown, parseCompletedLessons } from "./course.js";

describe("course helpers", () => {
  it("removes repository navigation around lesson markdown", () => {
    const source = "[目录](./README.md) · [下一章](./02.md)\n\n---\n\n# 第一章\n\n正文\n\n---\n\n[上一章](./00.md) · [目录](./README.md)";
    expect(cleanCourseMarkdown(source)).toBe("# 第一章\n\n正文");
  });

  it("keeps only known completed lesson ids", () => {
    expect(parseCompletedLessons(JSON.stringify([COURSE_LESSONS[0].id, "unknown"]))).toEqual([COURSE_LESSONS[0].id]);
    expect(parseCompletedLessons("not-json")).toEqual([]);
  });
});
