const FUNCTIONS = new Set(["sin", "cos", "tan", "log", "ln", "pi", "theta"]);
// A group in brackets, or a run of letters, digits and dots.
const OPERAND = String.raw`(\([^()]*\)|[\w.]+)`;

function unbracket(text: string): string {
  return text.startsWith("(") && text.endsWith(")") ? text.slice(1, -1) : text;
}

/** sqrt(…) with nested brackets, which a regular expression can't match. */
function squareRoots(text: string): string {
  let out = "";
  let rest = text;
  for (let at = rest.indexOf("sqrt("); at !== -1; at = rest.indexOf("sqrt(")) {
    let depth = 0;
    let end = at + 4;
    for (; end < rest.length; end++) {
      if (rest[end] === "(") depth++;
      if (rest[end] === ")" && --depth === 0) break;
    }
    if (end >= rest.length) break;
    out += `${rest.slice(0, at)}\\sqrt{${squareRoots(rest.slice(at + 5, end))}}`;
    rest = rest.slice(end + 1);
  }
  return out + rest;
}

/**
 * A line typed the way students write maths (x^2, 3/4, sqrt(10), 2*3, <=) as LaTeX, for a live
 * preview. Runs of words stay as text, so "add them: 2x = 14" reads naturally.
 */
export function typedToLatex(line: string): string {
  return squareRoots(line.trim())
    .replace(/[%#&]/g, (c) => `\\${c}`)
    .replace(/\^\(([^()]*)\)/g, "^{$1}")
    .replace(/\^(-?[\d.]+)/g, "^{$1}")
    .replace(new RegExp(`${OPERAND}\\/${OPERAND}`, "g"), (_, top: string, bottom: string) => {
      return `\\frac{${unbracket(top)}}{${unbracket(bottom)}}`;
    })
    .replace(/\*/g, String.raw`\times `)
    .replace(/<=/g, String.raw`\le `)
    .replace(/>=/g, String.raw`\ge `)
    .replace(/!=/g, String.raw`\ne `)
    .replace(/(?<![\\\w])([A-Za-z]{3,}(?:[\s,']+(?!(?:pi|ln)\b)[A-Za-z]+)*)(?!\w)/g, (words) => {
      const name = words.toLowerCase();
      return FUNCTIONS.has(name) ? `\\${name} ` : `\\text{ ${words} }`;
    })
    .replace(/(?<![\\\w])(pi|ln)(?!\w)/g, "\\$1 ");
}

/** Markdown for a step's preview: steps already in $…$ (from a maths editor) pass through. */
export function stepPreview(step: string): string {
  return step.includes("$") ? step : `$${typedToLatex(step)}$`;
}
