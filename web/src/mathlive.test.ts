import { describe, expect, it } from "vitest";

import { fieldLatex, placeholderLatex, stepValue } from "./mathlive";
import { stepPreview } from "./typedMaths";

describe("maths field values", () => {
  it("stores a field's LaTeX as $…$, which the preview, chat and server read as maths", () => {
    expect(stepValue("\\frac{3}{4}x=6")).toBe("$\\frac{3}{4}x=6$");
    expect(stepPreview(stepValue("x^2=9"))).toBe("$x^2=9$");
  });

  it("stores an empty field as an empty step, so it doesn't count as working", () => {
    expect(stepValue("  ")).toBe("");
  });

  it("round-trips a stored step back into the field", () => {
    expect(fieldLatex(stepValue("(x+7)(x+2)=0"))).toBe("(x+7)(x+2)=0");
  });

  it("converts working typed before the maths field loaded", () => {
    expect(fieldLatex("x^2 = 9")).toBe("x^{2} = 9");
    expect(fieldLatex("")).toBe("");
  });

  it("shows a placeholder as text, without letting it inject commands", () => {
    expect(placeholderLatex("Step 1")).toBe("\\text{Step 1}");
    expect(placeholderLatex("a}\\b{c")).toBe("\\text{abc}");
  });
});
