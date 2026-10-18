export type Role = "tutor" | "student";

export interface Me {
  id: string;
  email: string;
  display_name: string;
  role: Role;
  status: string;
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

const UNAVAILABLE = "Prof AI is unavailable right now. Try again later.";

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

export async function getJson<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const fetchFn = options.fetchFn ?? fetch;
  const redirectToSignIn = options.redirectToSignIn ?? redirectBrowserToSignIn;
  let response: Response;
  try {
    // Easy Auth answers an expired session with 401 for XHR, or with a cross-origin redirect
    // to sign-in that fetch can't follow; "manual" turns the latter into an opaque response.
    response = await fetchFn(path, {
      headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
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
  return (await response.json()) as T;
}

export function getMe(options?: ApiOptions): Promise<Me> {
  return getJson<Me>("/api/me", options);
}
