import { DESCRIBE_CHECKLIST } from "./lessons";

const MAX_DESCRIPTION_CHARS = 4000;

/** Describe a lesson in your own words; Prof AI drafts the form's fields from it. */
export function DescribeLesson({
  description,
  onChange,
  unanswered,
  busy,
  onDraft,
  onClose,
}: {
  description: string;
  onChange: (text: string) => void;
  /** Checklist ids the last draft found no answer to; null before the first draft. */
  unanswered: string[] | null;
  busy: boolean;
  onDraft: () => void;
  onClose: () => void;
}) {
  return (
    <div className="describe-panel">
      <p className="lesson-hint">
        Describe the lesson in your own words, typed or dictated. Prof AI fills in the title,
        topics, notes and level for you to check. Try to cover:
      </p>
      <ul className="describe-checklist">
        {DESCRIBE_CHECKLIST.map((item) => {
          const missed = unanswered?.includes(item.id) ?? false;
          return (
            <li key={item.id} className={missed ? "missed" : undefined}>
              {item.question}
              {missed && <span className="describe-missed"> Not in your description</span>}
            </li>
          );
        })}
      </ul>
      <textarea
        rows={5}
        maxLength={MAX_DESCRIPTION_CHARS}
        value={description}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Describe the lesson"
        placeholder="Year 9, simultaneous equations by elimination. They've done substitution but get muddled when the signs are negative, so go slowly…"
      />
      <div className="page-pick-actions">
        <button
          type="button"
          className="primary"
          disabled={busy || !description.trim()}
          onClick={onDraft}
        >
          {unanswered === null ? "Draft the lesson" : "Draft it again"}
        </button>
        <button type="button" className="secondary" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
