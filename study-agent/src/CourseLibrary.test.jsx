import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { CourseMarkdown } from "./CourseLibrary.jsx";

describe("CourseMarkdown", () => {
  it("highlights fenced C++ code without highlighting plain text blocks", () => {
    const html = renderToStaticMarkup(
      <CourseMarkdown>{[
        "```cpp",
        "int main() { return 0; }",
        "```",
        "",
        "```text",
        "input 42",
        "```",
      ].join("\n")}</CourseMarkdown>,
    );

    expect(html).toContain('class="hljs language-cpp"');
    expect(html).toContain('class="hljs-keyword"');
    expect(html).toContain('<code class="language-text">input 42');
  });
});
