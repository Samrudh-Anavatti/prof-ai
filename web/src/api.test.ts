import { describe, expect, it, vi } from "vitest";

import { ApiError, getMe, signInUrl, type Me } from "./api";

const ME: Me = {
  id: "oid-1",
  email: "alex@example.com",
  display_name: "Alex",
  role: "student",
  status: "active",
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
