import { useState, type KeyboardEvent } from "react";

import type { QuestionOverview, QuestionProgress } from "./api";
import { doneCount, progressOf } from "./progress";

/** Previous and next, where you are, a progress strip, and a grid to jump to any question. */
export function QuestionNav({
  questions,
  progress,
  current,
  onSelect,
  describe,
}: {
  questions: QuestionOverview[];
  progress: QuestionProgress[];
  current: string | null;
  onSelect: (number: string) => void;
  /** A question's progress in words, for the grid's labels. */
  describe: (progress: QuestionProgress | undefined) => string;
}) {
  const [open, setOpen] = useState(false);
  const index = questions.findIndex((q) => q.number === current);
  const previous = index > 0 ? questions[index - 1] : undefined;
  const next = index >= 0 && index < questions.length - 1 ? questions[index + 1] : undefined;

  function select(number: string) {
    setOpen(false);
    onSelect(number);
  }

  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape" && open) {
      event.stopPropagation();
      setOpen(false);
    }
  }

  return (
    <nav className="question-nav" aria-label="Questions" onKeyDown={onKeyDown}>
      <div className="question-nav-bar">
        <button
          type="button"
          className="nav-step"
          aria-label="Previous question"
          disabled={!previous}
          onClick={() => previous && select(previous.number)}
        >
          <span aria-hidden="true">‹</span>
        </button>
        <button
          type="button"
          className="question-jump"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          <span>Question {current}</span>
          <span className="question-position">
            {index + 1} of {questions.length}
          </span>
          <span className="jump-caret" aria-hidden="true">
            ▾
          </span>
        </button>
        <button
          type="button"
          className="nav-step"
          aria-label="Next question"
          disabled={!next}
          onClick={() => next && select(next.number)}
        >
          <span aria-hidden="true">›</span>
        </button>
        <span className="question-done muted">
          {doneCount(progress)} of {questions.length} done
        </span>
      </div>
      <ol className="progress-strip" aria-hidden="true">
        {questions.map((q) => (
          <li
            key={q.number}
            className={`strip-${progressOf(progress, q.number)?.status ?? "not_started"}`}
            data-current={q.number === current || undefined}
          />
        ))}
      </ol>
      {open && (
        <ul className="question-grid">
          {questions.map((q) => {
            const questionProgress = progressOf(progress, q.number);
            const status = questionProgress?.status ?? "not_started";
            return (
              <li key={q.number}>
                <button
                  type="button"
                  className={`question-chip ${status}`}
                  aria-current={q.number === current ? "step" : undefined}
                  aria-label={`Question ${q.number}: ${describe(questionProgress)}`}
                  onClick={() => select(q.number)}
                >
                  {q.number}
                  {status === "correct" && " ✓"}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </nav>
  );
}
