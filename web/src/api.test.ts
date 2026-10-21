import { describe, expect, it, vi } from "vitest";

import {
  ApiError,
  deleteUser,
  getMe,
  inviteUser,
  lockUser,
  saveTeachingStyle,
  sendMessage,
  signInUrl,
  type Me,
  type TeachingStyle,
} from "./api";

const ME: Me = {
  id: "oid-1",
  email: "alex@example.com",
  display_name: "Alex",
  role: "student",
  status: "active",
  is_admin: false,
};

const UNAVAILABLE = "Prof AI is unavailable right now. Try again later.";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function fakeFetch(result: Response | Error) {
  return vi.fn<typeof fetch>(async () => {
    if (result instanceof Error) throw result;
    return result;
  });
}

describe("getMe", () => {
  it("returns the signed-in user from /api/me", async () => {
    const fetchFn = fakeFetch(jsonResponse(200, ME));
    await expect(getMe({ fetchFn })).resolves.toEqual(ME);
    expect(fetchFn).toHaveBeenCalledWith(
      "/api/me",
      expect.objectContaining({
        redirect: "manual",
        headers: expect.objectContaining({ "X-Requested-With": "XMLHttpRequest" }),
      }),
    );
  });

  it("sends the browser to sign-in on 401", async () => {
    const redirectToSignIn = vi.fn();
    const fetchFn = fakeFetch(jsonResponse(401, { detail: "Not signed in." }));
    await expect(getMe({ fetchFn, redirectToSignIn })).rejects.toMatchObject({ status: 401 });
    expect(redirectToSignIn).toHaveBeenCalledOnce();
  });

  it("sends the browser to sign-in when Easy Auth redirects", async () => {
    const redirectToSignIn = vi.fn();
    const opaque = { type: "opaqueredirect", status: 0, ok: false } as Response;
    await expect(getMe({ fetchFn: fakeFetch(opaque), redirectToSignIn })).rejects.toBeInstanceOf(
      ApiError,
    );
    expect(redirectToSignIn).toHaveBeenCalledOnce();
  });

  it("surfaces the server's message for an uninvited or locked account", async () => {
    const redirectToSignIn = vi.fn();
    const locked = jsonResponse(403, { detail: "This account is locked. Ask your tutor." });
    await expect(getMe({ fetchFn: fakeFetch(locked), redirectToSignIn })).rejects.toMatchObject({
      status: 403,
      message: "This account is locked. Ask your tutor.",
    });
    expect(redirectToSignIn).not.toHaveBeenCalled();
  });

  it("hides server detail on 5xx and network failures", async () => {
    const down = fakeFetch(jsonResponse(503, { detail: "User store is unavailable." }));
    await expect(getMe({ fetchFn: down })).rejects.toMatchObject({
      status: 503,
      message: UNAVAILABLE,
    });
    const offline = fakeFetch(new TypeError("Failed to fetch"));
    await expect(getMe({ fetchFn: offline })).rejects.toMatchObject({
      status: 0,
      message: UNAVAILABLE,
    });
  });
});

describe("signInUrl", () => {
  it("returns to the current page after sign-in", () => {
    expect(signInUrl("/assignments?week=3")).toBe(
      "/.auth/login/aad?post_login_redirect_uri=%2Fassignments%3Fweek%3D3",
    );
  });
});

function sseResponse(...events: [string, unknown][]): Response {
  const text = events.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  return new Response(text.join(""), {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

describe("sendMessage", () => {
  const noop = { onDelta: () => {} };

  it("streams deltas and resolves with the title and whether Prof AI replied", async () => {
    const fetchFn = fakeFetch(
      sseResponse(
        ["delta", { text: "Hel" }],
        ["delta", { text: "lo" }],
        ["done", { title: "Fractions", ai: true }],
      ),
    );
    const deltas: string[] = [];
    const result = await sendMessage("c1", "hi", { onDelta: (t) => deltas.push(t) }, { fetchFn });
    expect(deltas).toEqual(["Hel", "lo"]);
    expect(result).toEqual({ title: "Fractions", ai: true });
    const [path, init] = fetchFn.mock.calls[0];
    expect(path).toBe("/api/chat/conversations/c1/messages");
    expect(init).toMatchObject({ method: "POST", body: JSON.stringify({ content: "hi" }) });
  });

  it("rejects with the server's message on an error event", async () => {
    const message = "Sorry, I can't help with that.";
    const fetchFn = fakeFetch(sseResponse(["delta", { text: "x" }], ["error", { message }]));
    await expect(sendMessage("c1", "hi", noop, { fetchFn })).rejects.toMatchObject({ message });
  });

  it("rejects when the stream ends without finishing", async () => {
    const fetchFn = fakeFetch(sseResponse(["delta", { text: "Hel" }]));
    await expect(sendMessage("c1", "hi", noop, { fetchFn })).rejects.toMatchObject({
      message: UNAVAILABLE,
    });
  });

  it("surfaces refusals such as the daily allowance", async () => {
    const detail = "You've used today's chat allowance. It resets at midnight UTC.";
    const fetchFn = fakeFetch(jsonResponse(429, { detail }));
    await expect(sendMessage("c1", "hi", noop, { fetchFn })).rejects.toMatchObject({
      status: 429,
      message: detail,
    });
  });
});

describe("saveTeachingStyle", () => {
  const STYLE: TeachingStyle = { content: "Be brief.", system_prompt: "...", max_bytes: 8192 };

  it("PUTs the content as JSON and returns the saved style", async () => {
    const fetchFn = fakeFetch(jsonResponse(200, STYLE));
    await expect(saveTeachingStyle("Be brief.", { fetchFn })).resolves.toEqual(STYLE);
    const [path, init] = fetchFn.mock.calls[0];
    expect(path).toBe("/api/teaching-style");
    expect(init).toMatchObject({
      method: "PUT",
      body: JSON.stringify({ content: "Be brief." }),
      headers: expect.objectContaining({ "Content-Type": "application/json" }),
    });
  });

  it("surfaces validation errors from the server", async () => {
    const detail = "The profile is 9000 bytes; the limit is 8192.";
    const fetchFn = fakeFetch(jsonResponse(400, { detail }));
    await expect(saveTeachingStyle("x", { fetchFn })).rejects.toMatchObject({
      status: 400,
      message: detail,
    });
  });
});

describe("user admin", () => {
  it("invites with a JSON POST", async () => {
    const created = { id: "invite-1", email: "cara@example.com", status: "invited" };
    const fetchFn = fakeFetch(jsonResponse(201, created));
    const user = { email: "cara@example.com", display_name: "Cara", role: "student" as const };
    await expect(inviteUser(user, { fetchFn })).resolves.toEqual(created);
    const [path, init] = fetchFn.mock.calls[0];
    expect(path).toBe("/api/users");
    expect(init).toMatchObject({ method: "POST", body: JSON.stringify(user) });
  });

  it("locks with a reason", async () => {
    const fetchFn = fakeFetch(jsonResponse(200, { id: "a/b" }));
    await lockUser("a/b", "Spam", { fetchFn });
    const [path, init] = fetchFn.mock.calls[0];
    expect(path).toBe("/api/users/a%2Fb/lock");
    expect(init).toMatchObject({ method: "POST", body: JSON.stringify({ reason: "Spam" }) });
  });

  it("deletes without reading a body from the 204", async () => {
    const fetchFn = fakeFetch(new Response(null, { status: 204 }));
    await expect(deleteUser("alex", { fetchFn })).resolves.toBeUndefined();
    expect(fetchFn.mock.calls[0][1]).toMatchObject({ method: "DELETE" });
  });

  it("surfaces refusals such as deleting a tutor with students", async () => {
    const detail = "punji@example.com still has students. Remove them first.";
    const fetchFn = fakeFetch(jsonResponse(400, { detail }));
    await expect(deleteUser("punji", { fetchFn })).rejects.toMatchObject({ message: detail });
  });
});
