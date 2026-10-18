import { describe, expect, it } from "vitest";

import { createSseParser } from "./sse";

function collect(chunks: string[]) {
  const events: [string, Record<string, unknown>][] = [];
  const parser = createSseParser((event, data) => events.push([event, data]));
  chunks.forEach((chunk) => parser.push(chunk));
  return events;
}

describe("createSseParser", () => {
  it("parses events the server sends", () => {
    expect(
      collect(['event: delta\ndata: {"text": "Hi"}\n\nevent: done\ndata: {"title": "t"}\n\n']),
    ).toEqual([
      ["delta", { text: "Hi" }],
      ["done", { title: "t" }],
    ]);
  });

  it("handles events split across chunks and CRLF line endings", () => {
    expect(collect(["event: del", 'ta\r\ndata: {"te', 'xt": "a"}\r', "\n\r\n"])).toEqual([
      ["delta", { text: "a" }],
    ]);
  });

  it("drops malformed events without throwing", () => {
    expect(collect(["event: delta\ndata: {nope\n\nevent: done\ndata: {}\n\n"])).toEqual([
      ["done", {}],
    ]);
  });
});
