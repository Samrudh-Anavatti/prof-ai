import { useEffect, useState } from "react";

import { ApiError, getMe, type Me } from "./api";
import { ChatPage } from "./ChatPage";
import { Logo } from "./Logo";

type State = { kind: "loading" } | { kind: "ready"; me: Me } | { kind: "error"; message: string };

const SIGN_OUT_URL = "/.auth/logout?post_logout_redirect_uri=/";

export function App() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    getMe()
      .then((me) => setState({ kind: "ready", me }))
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) return;
        const message = error instanceof ApiError ? error.message : "Something went wrong.";
        setState({ kind: "error", message });
      });
  }, []);

  return (
    <div className="app">
      <header className="top-bar">
        <Logo />
        {state.kind === "ready" && (
          <nav className="account">
            <span className="account-name">
              {state.me.display_name}
              {state.me.role === "tutor" && <span className="role-tag">Tutor</span>}
            </span>
            <a href={SIGN_OUT_URL}>Sign out</a>
          </nav>
        )}
        {state.kind === "error" && <a href={SIGN_OUT_URL}>Sign out</a>}
      </header>
      {state.kind === "loading" && <p className="centred muted">Loading…</p>}
      {state.kind === "error" && (
        <div className="centred">
          <div className="notice" role="alert">
            {state.message}
          </div>
        </div>
      )}
      {state.kind === "ready" && <ChatPage me={state.me} />}
    </div>
  );
}
