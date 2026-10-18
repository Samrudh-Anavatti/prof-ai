export type SseHandler = (event: string, data: Record<string, unknown>) => void;

/** Parses server-sent events from text chunks that may split anywhere. */
export function createSseParser(onEvent: SseHandler) {
  let buffer = "";
  return {
    push(chunk: string) {
      buffer = (buffer + chunk).replace(/\r\n/g, "\n");
      let end = buffer.indexOf("\n\n");
      while (end !== -1) {
        const block = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        let event = "message";
        let data = "";
        for (const line of block.split("\n")) {
          if (line.startsWith("event: ")) event = line.slice(7);
          else if (line.startsWith("data: ")) data += line.slice(6);
        }
        if (data) {
          try {
            onEvent(event, JSON.parse(data) as Record<string, unknown>);
          } catch {
            // A malformed event is dropped; the stream's done/error event decides the outcome.
          }
        }
        end = buffer.indexOf("\n\n");
      }
    },
  };
}
