import { describe, expect, it, vi } from "vitest";

import {
  changeStudentChatModel,
  createStudentChat,
  setPreferredModel,
  type ModelList,
  type ModelOption,
} from "./api";
import { initialModel, modelAllowed, modelSummary } from "./lessons";

function option(id: string, approved: boolean, typical = 0.0015): ModelOption {
  return {
    id,
    label: id,
    provider: approved ? "foundry" : "ollama",
    approved_for_student_conversations: approved,
    context_window: 1_000_000,
    input_usd_per_m: 0.2,
    cached_input_usd_per_m: 0.02,
    output_usd_per_m: 1.2,
    typical_message_usd: typical,
    notes: "Notes.",
  };
}

const LIST: ModelList = {
  models: [option("luna", true), option("glm", false)],
  default: "luna",
  preferred: "glm",
};

function jsonFetch() {
  return vi.fn<typeof fetch>(async () => new Response(JSON.stringify({})));
}

describe("choosing a model", () => {
  it("only offers approved models for a student's chat", () => {
    expect(modelAllowed(option("glm", false), true)).toBe(false);
    expect(modelAllowed(option("glm", false), false)).toBe(true);
  });

  it("starts from the tutor's preferred model only where it's allowed", () => {
    expect(initialModel(LIST, false)).toBe("glm");
    expect(initialModel(LIST, true)).toBe("luna");
    expect(initialModel({ ...LIST, preferred: null }, false)).toBe("luna");
  });

  it("describes cost per message and the notes", () => {
    expect(modelSummary(option("luna", true, 0.0015))).toBe("about 0.15¢ a message · Notes.");
    expect(modelSummary(option("big", true, 0.05))).toBe("about $0.050 a message · Notes.");
  });
});

describe("model API calls", () => {
  it("sends a model with a new chat only when one is chosen", async () => {
    const lesson = { title: "Ratios", topics: [], notes: "", material: "", sources: [] };
    const fetchFn = jsonFetch();
    await createStudentChat("alex", lesson, false, { fetchFn }, "luna");
    await createStudentChat("alex", lesson, false, { fetchFn });
    const bodies = fetchFn.mock.calls.map(([, init]) => JSON.parse(String(init?.body)));
    expect(bodies[0].model).toBe("luna");
    expect("model" in bodies[1]).toBe(false);
  });

  it("changes a chat's model and the tutor's default", async () => {
    const fetchFn = jsonFetch();
    await changeStudentChatModel("alex", "c1", "luna", { fetchFn });
    await setPreferredModel(null, { fetchFn });
    const calls = fetchFn.mock.calls.map(([path, init]) => [path, init?.method, init?.body]);
    expect(calls).toEqual([
      ["/api/students/alex/chats/c1", "PATCH", JSON.stringify({ model: "luna" })],
      ["/api/models/preferred", "PUT", JSON.stringify({ model: null })],
    ]);
  });
});
