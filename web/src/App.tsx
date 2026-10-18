import { useEffect, useState } from "react";

import { ApiError, getMe, type Me } from "./api";

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
    <div className="page">
      <header className="top-bar">
        <span className="brand">Prof AI</span>
        {state.kind !== "loading" && <a href={SIGN_OUT_URL}>Sign out</a>}
      </header>
      <main className="content">
        {state.kind === "loading" && <p className="muted">Loading…</p>}
        {state.kind === "error" && (
          <div className="notice" role="alert">
            {state.message}
          </div>
        )}
        {state.kind === "ready" && <Welcome me={state.me} />}
      </main>
    </div>
  );
}

function Welcome({ me }: { me: Me }) {
  return (
    <section>
      <h1>Hi, {me.display_name}</h1>
      <p className="muted">
        {me.role === "tutor"
          ? "Your tutor dashboard is on its way."
          : "Your assignments will appear here."}
      </p>
    </section>
  );
}
