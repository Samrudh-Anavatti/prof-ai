import type { FormEvent, KeyboardEvent, RefObject } from "react";

export type Recipient = "ai" | "tutor" | "student";

export const RECIPIENT_LABELS: Record<Recipient, string> = {
  ai: "Prof AI",
  tutor: "My tutor",
  student: "Student",
};

const PLACEHOLDERS: Record<Recipient, string> = {
  ai: "Ask Prof AI…",
  tutor: "Write to your tutor only…",
  student: "Write to your student (Prof AI won't reply)…",
};

export const MAX_INPUT_CHARS = 2000;

/** The message box, with a "Send to" choice when there's more than one recipient. */
export function Composer({
  value,
  onChange,
  onSend,
  options,
  recipient,
  onRecipient,
  ready,
  sending,
  textareaRef,
}: {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  options: Recipient[];
  recipient: Recipient;
  onRecipient: (recipient: Recipient) => void;
  /** False until the chat has loaded. */
  ready: boolean;
  sending: boolean;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
}) {
  function submit(event: FormEvent) {
    event.preventDefault();
    onSend();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSend();
    }
  }

  return (
    <form className="composer" onSubmit={submit}>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        maxLength={MAX_INPUT_CHARS}
        rows={2}
        placeholder={PLACEHOLDERS[recipient]}
        aria-label="Message"
        disabled={!ready}
      />
      <div className="composer-actions">
        {options.length > 1 && (
          <div className="recipient-toggle" role="radiogroup" aria-label="Send to">
            {options.map((option) => (
              <button
                key={option}
                type="button"
                role="radio"
                aria-checked={option === recipient}
                onClick={() => {
                  onRecipient(option);
                  textareaRef.current?.focus();
                }}
              >
                {RECIPIENT_LABELS[option]}
              </button>
            ))}
          </div>
        )}
        <button
          type="submit"
          className={recipient === "ai" ? "ask-ai" : undefined}
          disabled={sending || !ready || !value.trim()}
        >
          Send
        </button>
      </div>
    </form>
  );
}
