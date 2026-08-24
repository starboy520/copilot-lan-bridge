import { describe, expect, it } from "vitest";
import { takeNdjsonLines } from "./stream.js";

describe("takeNdjsonLines", () => {
  it("keeps an incomplete event for the next chunk", () => {
    const first = takeNdjsonLines("", '{"type":"delta","text":"你');
    expect(first.events).toEqual([]);
    const second = takeNdjsonLines(first.remainder, '好"}\n{"type":"done"}\n');
    expect(second.events).toEqual([
      { type: "delta", text: "你好" },
      { type: "done" },
    ]);
    expect(second.remainder).toBe("");
  });
});
