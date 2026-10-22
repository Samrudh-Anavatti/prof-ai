/** Keys that only mean something in maths. Typed among words, they start maths. */
export const MATHS_KEYS = new Set(["=", "+", "^", "/", "*", "<", ">"]);

const MATHS_NAMES = new Set([
  "sin",
  "cos",
  "tan",
  "sec",
  "csc",
  "cot",
  "sinh",
  "cosh",
  "tanh",
  "arcsin",
  "arccos",
  "arctan",
  "log",
  "ln",
  "exp",
  "lim",
  "max",
  "min",
  "mod",
  "gcd",
  "lcm",
  "sqrt",
  "pi",
  "theta",
  "alpha",
  "beta",
  "gamma",
  "delta",
  "lambda",
  "sigma",
  "phi",
  "omega",
]);
// Two letters are usually variables multiplied, as in xy; these are the words students write.
const SHORT_WORDS = new Set([
  "am",
  "an",
  "as",
  "at",
  "be",
  "by",
  "do",
  "if",
  "in",
  "is",
  "it",
  "my",
  "no",
  "of",
  "on",
  "or",
  "so",
  "to",
  "up",
  "us",
  "we",
]);

/** Whether letters typed in maths were really a word, so the line should go back to words. */
export function isWord(letters: string): boolean {
  const lower = letters.toLowerCase();
  if (MATHS_NAMES.has(lower)) return false;
  return lower.length >= 3 || SHORT_WORDS.has(lower);
}

/** The maths at the end of some words, such as "x + 3" in "so x + 3": everything after the
 * last word. from is where it starts. */
export function mathsTail(text: string): { from: number; maths: string } {
  let end = 0;
  for (const match of text.matchAll(/[A-Za-z]+/g)) {
    if (isWord(match[0])) end = match.index + match[0].length;
  }
  const rest = text.slice(end);
  return { from: end + rest.length - rest.trimStart().length, maths: rest.trim() };
}
