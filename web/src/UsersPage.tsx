import { useEffect, useState, type FormEvent } from "react";

import {
  ApiError,
  deleteUser,
  inviteUser,
  listUsers,
  lockUser,
  UNAVAILABLE,
  unlockUser,
  type Me,
  type Role,
  type UserView,
} from "./api";

const STATUS_LABELS = { invited: "Invited", active: "Active", account_locked: "Locked" };
const SIGN_UP_URL = `${window.location.origin}/.auth/login/aad?prompt=create&post_login_redirect_uri=/`;

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : UNAVAILABLE;
}

function byName(a: UserView, b: UserView): number {
  return a.display_name.localeCompare(b.display_name);
}

export function UsersPage({ me }: { me: Me }) {
  const [users, setUsers] = useState<UserView[] | null>(null);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("student");
  const [tutorEmail, setTutorEmail] = useState(me.email);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [invited, setInvited] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    listUsers()
      .then(setUsers)
      .catch((e: unknown) => setError(messageOf(e)));
  }, []);

  async function act(work: () => Promise<string>) {
    setBusy(true);
    setError(null);
    setStatus(null);
    setInvited(null);
    try {
      setStatus(await work());
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  }

  function replace(updated: UserView) {
    setUsers((current) => (current ?? []).map((u) => (u.id === updated.id ? updated : u)));
  }

  function invite(event: FormEvent) {
    event.preventDefault();
    void act(async () => {
      const user = await inviteUser({
        email,
        display_name: name,
        role,
        ...(role === "student" ? { tutor_email: tutorEmail } : {}),
      });
      setUsers((current) => [...(current ?? []), user]);
      setEmail("");
      setName("");
      setInvited(user.email);
      setCopied(false);
      return `Invited ${user.email}.`;
    });
  }

  function lock(user: UserView) {
    const reason = window.prompt(`Why are you locking ${user.display_name}'s account?`);
    if (!reason?.trim()) return;
    void act(async () => {
      replace(await lockUser(user.id, reason));
      return `Locked ${user.email}. They can't use Prof AI until you unlock them.`;
    });
  }

  function unlock(user: UserView) {
    void act(async () => {
      replace(await unlockUser(user.id));
      return `Unlocked ${user.email}.`;
    });
  }

  function remove(user: UserView) {
    const confirmed = window.confirm(
      `Delete ${user.display_name} (${user.email})? This permanently deletes their account, chats and profile.`,
    );
    if (!confirmed) return;
    void act(async () => {
      await deleteUser(user.id);
      setUsers((current) => (current ?? []).filter((u) => u.id !== user.id));
      return `Deleted ${user.email} and their data.`;
    });
  }

  if (users === null) {
    return (
      <div className="centred">
        {error ? (
          <div className="notice" role="alert">
            {error}
          </div>
        ) : (
          <p className="muted">Loading…</p>
        )}
      </div>
    );
  }

  const tutors = users.filter((u) => u.role === "tutor" && u.status !== "invited").sort(byName);
  const sorted = [...users].sort(
    (a, b) => Number(b.id === me.id) - Number(a.id === me.id) || byName(a, b),
  );

  return (
    <main className="admin-page">
      <h1>{me.is_admin ? "Users" : "Your students"}</h1>
      <p className="muted">
        {me.is_admin
          ? "You're an admin: you can invite tutors and students and manage every account."
          : "Invite your students and manage their accounts. Their chats use your teaching style."}
      </p>

      <form className="invite-form" onSubmit={invite}>
        <h2>Invite someone</h2>
        <div className="invite-fields">
          <label>
            Email
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="off"
            />
          </label>
          <label>
            First name
            <input required value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          {me.is_admin && (
            <label>
              Role
              <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
                <option value="student">Student</option>
                <option value="tutor">Tutor</option>
              </select>
            </label>
          )}
          {me.is_admin && role === "student" && (
            <label>
              Tutor
              <select value={tutorEmail} onChange={(e) => setTutorEmail(e.target.value)}>
                {tutors.map((t) => (
                  <option key={t.id} value={t.email}>
                    {t.display_name} ({t.email})
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        <button type="submit" className="primary" disabled={busy}>
          Invite
        </button>
      </form>

      {invited && (
        <div className="signup-link">
          <p>
            Send <strong>{invited}</strong> this link to create their account. They'll be emailed a
            code, which can take a few minutes and may land in spam.
          </p>
          <div className="signup-link-row">
            <a href={SIGN_UP_URL} target="_blank" rel="noreferrer">
              {SIGN_UP_URL}
            </a>
            <button
              type="button"
              className="secondary"
              onClick={() =>
                void navigator.clipboard.writeText(SIGN_UP_URL).then(() => setCopied(true))
              }
            >
              {copied ? "Copied" : "Copy link"}
            </button>
          </div>
        </div>
      )}
      {status && (
        <p className="admin-status" role="status">
          {status}
        </p>
      )}
      {error && (
        <div className="notice" role="alert">
          {error}
        </div>
      )}

      <ul className="user-list">
        {sorted.map((user) => (
          <li key={user.id} className="user-row">
            <div className="user-main">
              <span className="user-name">
                {user.display_name}
                {user.id === me.id && <span className="role-tag">You</span>}
                {user.is_admin && <span className="role-tag">Admin</span>}
              </span>
              <span className="muted user-email">{user.email}</span>
            </div>
            <div className="user-meta">
              <span className="muted">
                {user.role === "tutor" ? "Tutor" : "Student"}
                {me.is_admin && user.tutor_email && ` · tutor ${user.tutor_email}`}
              </span>
              <span className={`pill ${user.status}`}>{STATUS_LABELS[user.status]}</span>
            </div>
            {user.id !== me.id && (
              <div className="user-actions">
                {user.status === "active" && (
                  <button
                    type="button"
                    className="secondary"
                    disabled={busy}
                    onClick={() => lock(user)}
                  >
                    Lock
                  </button>
                )}
                {user.status === "account_locked" && (
                  <button
                    type="button"
                    className="secondary"
                    disabled={busy}
                    onClick={() => unlock(user)}
                  >
                    Unlock
                  </button>
                )}
                <button
                  type="button"
                  className="danger"
                  disabled={busy}
                  onClick={() => remove(user)}
                >
                  Delete
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </main>
  );
}
