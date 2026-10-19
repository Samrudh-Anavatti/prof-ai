import { useEffect, useState, type MouseEvent } from "react";

import { ApiError, getMe, type Me } from "./api";
import { ChatPage } from "./ChatPage";
import { LessonsPage } from "./LessonsPage";
import { Logo } from "./Logo";
import { TeachingStylePage } from "./TeachingStylePage";
import { TutorChatPage } from "./TutorChatPage";
import { UsersPage } from "./UsersPage";

type State = { kind: "loading" } | { kind: "ready"; me: Me } | { kind: "error"; message: string };

const SIGN_OUT_URL = "/.auth/logout?post_logout_redirect_uri=/";
const CHAT_PATH = "/";
const LESSONS_PATH = "/lessons";
const TEACHING_STYLE_PATH = "/teaching-style";
const USERS_PATH = "/users";
const TUTOR_PAGES = [
  { path: CHAT_PATH, label: "Chat" },
  { path: LESSONS_PATH, label: "Lessons" },
  { path: TEACHING_STYLE_PATH, label: "Teaching style" },
  { path: USERS_PATH, label: "Users" },
];
const STUDENT_CHAT_PATH = /^\/lessons\/([^/]+)\/([^/]+)$/;
const UNSAVED_WARNING = "You have unsaved changes to your teaching style. Leave anyway?";

export function App() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [path, setPath] = useState(window.location.pathname);
  const [unsaved, setUnsaved] = useState(false);

  useEffect(() => {
    getMe()
      .then((me) => setState({ kind: "ready", me }))
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) return;
        const message = error instanceof ApiError ? error.message : "Something went wrong.";
        setState({ kind: "error", message });
      });
  }, []);

  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  function navigate(to: string) {
    if (to === path) return;
    window.history.pushState(null, "", to);
    setPath(to);
    setUnsaved(false);
  }

  function onNavClick(event: MouseEvent<HTMLAnchorElement>, to: string) {
    event.preventDefault();
    if (unsaved && !window.confirm(UNSAVED_WARNING)) return;
    navigate(to);
  }

  const isTutor = state.kind === "ready" && state.me.role === "tutor";
  const studentChat = isTutor ? STUDENT_CHAT_PATH.exec(path) : null;
  const page = studentChat
    ? LESSONS_PATH
    : isTutor && TUTOR_PAGES.some((p) => p.path === path)
      ? path
      : CHAT_PATH;

  return (
    <div className="app">
      <header className="top-bar">
        <Logo />
        {state.kind === "ready" && (
          <nav className="account">
            {isTutor &&
              TUTOR_PAGES.map((p) => (
                <a
                  key={p.path}
                  className={p.path === page ? "nav-link current" : "nav-link"}
                  href={p.path}
                  aria-current={p.path === page ? "page" : undefined}
                  onClick={(e) => onNavClick(e, p.path)}
                >
                  {p.label}
                </a>
              ))}
            <span className="account-name">
              {state.me.display_name}
              {isTutor && <span className="role-tag">Tutor</span>}
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
      {state.kind === "ready" && page === TEACHING_STYLE_PATH && (
        <TeachingStylePage onUnsavedChange={setUnsaved} onTryIt={() => navigate(CHAT_PATH)} />
      )}
      {state.kind === "ready" && studentChat && (
        <TutorChatPage
          me={state.me}
          studentId={decodeURIComponent(studentChat[1])}
          chatId={decodeURIComponent(studentChat[2])}
          onBack={() => navigate(LESSONS_PATH)}
        />
      )}
      {state.kind === "ready" && page === LESSONS_PATH && !studentChat && (
        <LessonsPage
          me={state.me}
          onOpenChat={(studentId, chatId) =>
            navigate(
              `${LESSONS_PATH}/${encodeURIComponent(studentId)}/${encodeURIComponent(chatId)}`,
            )
          }
        />
      )}
      {state.kind === "ready" && page === USERS_PATH && <UsersPage me={state.me} />}
      {state.kind === "ready" && page === CHAT_PATH && <ChatPage me={state.me} />}
    </div>
  );
}
