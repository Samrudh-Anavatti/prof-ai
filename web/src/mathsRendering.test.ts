import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Markdown, normaliseMaths, safeUrl } from "./Markdown";

function render(text: string): string {
  return renderToStaticMarkup(createElement(Markdown, { text }));
}

describe("Prof AI replies", () => {
  it("turn inline and display LaTeX into MathML", () => {
    const html = render("Half is $\\frac{1}{2}$.\n\n$$x^2 + 5 = 20$$");
    expect(html).toContain("<math");
    expect(html).toContain("<mfrac>");
    expect(html).toContain('display="block"');
    expect(html).not.toContain("$");
  });

  it("accept the other ways models write maths", () => {
    expect(normaliseMaths("so \\(x = 3\\) works")).toBe("so $x = 3$ works");
    expect(normaliseMaths("\\[x^2\\]")).toBe("\n$$\nx^2\n$$\n");
    expect(normaliseMaths("  $$a + b$$  ")).toBe("$$\na + b\n$$");
    expect(normaliseMaths("costs £5, then $x$")).toBe("costs £5, then $x$");
    expect(render("\\[\\frac{3}{4}\\]")).toContain('display="block"');
  });

  it("render simple Markdown", () => {
    const html = render("Try this:\n\n1. **Add** the parts\n2. Divide");
    expect(html).toContain("<ol>");
    expect(html).toContain("<strong>Add</strong>");
  });

  it("show raw HTML as text instead of running it", () => {
    const html = render('<script>alert(1)</script><b onclick="x()">hi</b>');
    expect(html).not.toContain("<script");
    expect(html).not.toContain("<b ");
    expect(html).toContain("&lt;script&gt;");
  });

  it("drop images and unsafe links", () => {
    expect(render("![x](https://example.com/x.png)")).not.toContain("<img");
    const html = render("[click](javascript:alert(1)) and [site](https://example.com)");
    expect(html).not.toContain("javascript:");
    expect(html).toContain('href="https://example.com"');
    expect(html).toContain('rel="noreferrer"');
  });

  it("allow only web and email links", () => {
    expect(safeUrl("https://example.com")).toBe("https://example.com");
    expect(safeUrl("mailto:tutor@example.com")).toBe("mailto:tutor@example.com");
    expect(safeUrl("javascript:alert(1)")).toBe("");
    expect(safeUrl("/api/users")).toBe("");
  });
});
