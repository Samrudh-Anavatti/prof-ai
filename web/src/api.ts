import { createSseParser } from "./sse";

export type Role = "tutor" | "student";

export interface Me {
  id: string;
  email: string;
  display_name: string;
  role: Role;
  status: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  updated_at: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  at: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: ChatMessage[];
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export interface ApiOptions {
  fetchFn?: typeof fetch;
  redirectToSignIn?: () => void;
}

export const UNAVAILABLE = "Prof AI is unavailable right now. Try again later.";

export function signInUrl(returnTo: string): string {
  return `/.auth/login/aad?post_login_redirect_uri=${encodeURIComponent(returnTo)}`;
}

function redirectBrowserToSignIn(): void {
  const { pathname, search } = window.location;
  window.location.assign(signInUrl(pathname + search));
}

async function errorDetail(response: Response): Promise<string | undefined> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    return undefined;
  }
  return undefined;
}

async function request(path: string, init: RequestInit, options: ApiOptions): Promise<Response> {
  const fetchFn = options.fetchFn ?? fetch;
  const redirectToSignIn = options.redirectToSignIn ?? redirectBrowserToSignIn;
  let response: Response;
  try {
    // Easy Auth answers an expired session with 401 for XHR, or with a cross-origin redirect
    // to sign-in that fetch can't follow; "manual" turns the latter into an opaque response.
    response = await fetchFn(path, {
      ...init,
      headers: {
        Accept: "application/json",
        "X-Requested-With": "XMLHttpRequest",
        ...init.headers,
      },
      redirect: "manual",
    });
  } catch {
    throw new ApiError(0, UNAVAILABLE);
  }
  if (response.status === 401 || response.type === "opaqueredirect") {
    redirectToSignIn();
    throw new ApiError(401, "Signing you in…");
  }
  if (!response.ok) {
    const detail = response.status >= 500 ? undefined : await errorDetail(response);
    throw new ApiError(response.status, detail ?? UNAVAILABLE);
  }
  return response;
}

export async function getJson<T>(path: string, options: ApiOptions = {}): Promise<T> {
  return (await (await request(path, {}, options)).json()) as T;
}

async function postJson<T>(path: string, body: unknown, options: ApiOptions = {}): Promise<T> {
  const response = await request(
    path,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    options,
  );
  return (await response.json()) as T;
}

export function getMe(options?: ApiOptions): Promise<Me> {
  return getJson<Me>("/api/me", options);
}

export function listConversations(options?: ApiOptions): Promise<ConversationSummary[]> {
  return getJson<ConversationSummary[]>("/api/chat/conversations", options);
}

export function startConversation(options?: ApiOptions): Promise<ConversationSummary> {
  return postJson<ConversationSummary>("/api/chat/conversations", {}, options);
}

export function getConversation(id: string, options?: ApiOptions): Promise<ConversationDetail> {
  return getJson<ConversationDetail>(`/api/chat/conversations/${encodeURIComponent(id)}`, options);
}

export interface ReplyHandlers {
  onDelta: (text: string) => void;
}

/** Streams the tutor's reply; resolves with the conversation title once it's saved. */
export async function sendMessage(
  conversationId: string,
  content: string,
  handlers: ReplyHandlers,
  options: ApiOptions = {},
): Promise<string> {
  const response = await request(
    `/api/chat/conversations/${encodeURIComponent(conversationId)}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ content }),
    },
    options,
  );
  let title: string | undefined;
  let failure: string | undefined;
  const parser = createSseParser((event, data) => {
    if (event === "delta" && typeof data.text === "string") handlers.onDelta(data.text);
    else if (event === "done") title = typeof data.title === "string" ? data.title : "";
    else if (event === "error") failure = typeof data.message === "string" ? data.message : "";
  });
  if (!response.body) throw new ApiError(0, UNAVAILABLE);
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    parser.push(value);
  }
  if (failure !== undefined) throw new ApiError(502, failure || UNAVAILABLE);
  if (title === undefined) throw new ApiError(0, UNAVAILABLE);
  return title;
}
