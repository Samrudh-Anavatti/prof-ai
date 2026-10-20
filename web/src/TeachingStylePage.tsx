import { useEffect, useState } from "react";

import {
  ApiError,
  getTeachingStyle,
  saveTeachingStyle,
  UNAVAILABLE,
  type TeachingStyle,
} from "./api";
import { PageSkeleton } from "./Skeleton";

const encoder = new TextEncoder();

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : UNAVAILABLE;
}

interface Props {
  onUnsavedChange: (unsaved: boolean) => void;
  onTryIt: () => void;
}

export function TeachingStylePage({ onUnsavedChange, onTryIt }: Props) {
  const [saved, setSaved] = useState<TeachingStyle | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getTeachingStyle()
      .then((style) => {
        setSaved(style);
        setDraft(style.content);
      })
      .catch((e: unknown) => setError(messageOf(e)));
  }, []);

  const unsaved = saved !== null && draft.trim() !== saved.content;
  useEffect(() => onUnsavedChange(unsaved), [unsaved, onUnsavedChange]);

  useEffect(() => {
    if (!unsaved) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [unsaved]);

  async function save(): Promise<boolean> {
    setSaving(true);
    setError(null);
    setStatus(null);
    try {
      const style = await saveTeachingStyle(draft);
      setSaved(style);
      setDraft(style.content);
      setStatus("Saved. Your next message, and your students', will use it.");
      return true;
    } catch (e) {
      setError(messageOf(e));
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function saveAndTry() {
    if (unsaved && !(await save())) return;
    onUnsavedChange(false);
    onTryIt();
  }

  if (saved === null) {
    return (
      <div className="centred">
        {error ? (
          <div className="notice" role="alert">
            {error}
          </div>
        ) : (
          <PageSkeleton />
        )}
      </div>
    );
  }

  const bytes = encoder.encode(draft.trim()).length;
  const tooLong = bytes > saved.max_bytes;

  return (
    <section className="style-page">
      <h1>Your teaching style</h1>
      <p className="muted">
        Tell Luna how you like to teach: tone, analogies, how to structure steps, what to praise.
        It's added to the tutor prompt for you and every student you tutor, from their next message.
        Markdown is fine.
      </p>

      <textarea
        className="style-editor"
        value={draft}
        onChange={(e) => {
          setDraft(e.target.value);
          setStatus(null);
        }}
        rows={14}
        aria-label="Teaching style"
        placeholder={
          "- Use football analogies where they fit.\n- One step at a time.\n- End with a quick check question."
        }
      />

      <div className="style-actions">
        <span className={tooLong ? "byte-count over" : "byte-count muted"}>
          {bytes.toLocaleString()} / {saved.max_bytes.toLocaleString()} bytes
          {unsaved && " · unsaved changes"}
        </span>
        <button
          type="button"
          className="secondary"
          onClick={() => void save()}
          disabled={saving || !unsaved || tooLong || !draft.trim()}
        >
          Save
        </button>
        <button
          type="button"
          className="primary"
          onClick={() => void saveAndTry()}
          disabled={saving || tooLong || !draft.trim()}
        >
          {unsaved ? "Save and try it" : "Try it in a new chat"}
        </button>
      </div>

      {status && (
        <p className="style-status" role="status">
          {status}
        </p>
      )}
      {error && (
        <div className="notice" role="alert">
          {error}
        </div>
      )}

      <details className="prompt-preview">
        <summary>What Luna is told in your chats (saved version)</summary>
        <p className="muted">
          The base tutor prompt, then your teaching style, then your own profile. Your students get
          the same, with their own profile instead of yours.
        </p>
        <pre>{saved.system_prompt}</pre>
      </details>
    </section>
  );
}
