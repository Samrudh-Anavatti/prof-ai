import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";

const SAFE_LINK = /^(https?:|mailto:)/i;

export function safeUrl(url: string): string {
  return SAFE_LINK.test(url) ? defaultUrlTransform(url) : "";
}

/**
 * Models write maths several ways. remark-math only treats $$ on lines of their own as display
 * maths, so rewrite \[…\], \(…\) and one-line $$…$$ into the forms it understands.
 */
export function normaliseMaths(text: string): string {
  return text
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, maths: string) => `\n$$\n${maths.trim()}\n$$\n`)
    .replace(/\\\((.+?)\\\)/g, (_, maths: string) => `$${maths.trim()}$`)
    .replace(/^[ \t]*\$\$([^\n$]+)\$\$[ \t]*$/gm, (_, maths: string) => `$$\n${maths.trim()}\n$$`);
}

/**
 * A Prof AI reply. Model output is untrusted: react-markdown never renders raw HTML, images
 * are dropped, and only http(s) and mailto links survive. KaTeX writes MathML, which browsers
 * draw natively, so the strict CSP needs no stylesheet, fonts or inline styles for it.
 */
export function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[[rehypeKatex, { output: "mathml", throwOnError: false }]]}
        disallowedElements={["img"]}
        urlTransform={safeUrl}
        components={{
          a: ({ href, children }) =>
            href ? (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            ) : (
              <span>{children}</span>
            ),
        }}
      >
        {normaliseMaths(text)}
      </ReactMarkdown>
    </div>
  );
}
