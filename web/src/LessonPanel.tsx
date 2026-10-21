import { useState, type FormEvent } from "react";

import {
  ApiError,
  UNAVAILABLE,
  type CheckOutcome,
  type LessonOverview,
  type QuestionProgress,
} from "./api";
import { Markdown } from "./Markdown";
import { doneCount, HELP_PROMPTS, progressLabel, progressOf } from "./progress";

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : UNAVAILABLE;
}

/** Worked examples, the questions and the current question, above a lesson chat. */
export function LessonPanel({
  lesson,
  progress,
  current,
  onSelect,
  onHelp,
  onCheck,
  busy,
}: {
  lesson: LessonOverview;
  progress: QuestionProgress[];
  current: string | null;
  onSelect: (number: string) => void;
  /** Students only: asks Prof AI about the current question. */
  onHelp?: (text: string) => void;
  /** Students only: checks an answer to the current question. */
  onCheck?: (number: string, answer: string) => Promise<CheckOutcome>;
  busy: boolean;
}) {
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<{ number: string; outcome: CheckOutcome } | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const examples = lesson.worked_examples ?? [];
  const questions = lesson.questions ?? [];
  const question = questions.find((q) => q.number === current);
  const shownResult = result && result.number === current ? result.outcome : null;

  function select(number: string) {
    setAnswer("");
    setError(null);
    onSelect(number);
  }

  async function check(event: FormEvent) {
    event.preventDefault();
    if (!question || !onCheck || !answer.trim()) return;
    setChecking(true);
    setError(null);
    try {
      const outcome = await onCheck(question.number, answer.trim());
      setResult({ number: question.number, outcome });
      if (outcome.correct) setAnswer("");
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setChecking(false);
    }
  }

  return (
    <section className="lesson-panel" aria-label="Lesson">
      {examples.length > 0 && (
        <details className="worked-examples" open={lesson.support === "step_by_step"}>
          <summary>
            Worked {examples.length === 1 ? "example" : "examples"} ({examples.length})
          </summary>
          {examples.map((example, index) => (
            <article key={index} className="worked-example">
              {example.title && <h3>{example.title}</h3>}
              <Markdown text={example.text} lineBreaks />
            </article>
          ))}
        </details>
      )}

      {questions.length > 0 && (
        <>
          <div className="question-nav">
            <span className="muted">
              {doneCount(progress)} of {questions.length} done
            </span>
            <div className="question-chips">
              {questions.map((q) => {
                const status = progressOf(progress, q.number)?.status ?? "not_started";
                return (
                  <button
                    key={q.number}
                    type="button"
                    className={`question-chip ${status}`}
                    aria-pressed={q.number === current}
                    aria-label={`Question ${q.number}: ${progressLabel(progressOf(progress, q.number))}`}
                    onClick={() => select(q.number)}
                  >
                    {q.number}
                    {status === "correct" && " ✓"}
                  </button>
                );
              })}
            </div>
          </div>

          {question && (
            <div className="question-card">
              <div className="question-head">
                <strong>Question {question.number}</strong>
                <span className="muted">
                  {progressLabel(progressOf(progress, question.number))}
                </span>
              </div>
              <Markdown text={question.text} lineBreaks />

              {onHelp && (
                <div className="help-buttons">
                  {HELP_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      className="starter"
                      disabled={busy}
                      onClick={() => onHelp(prompt)}
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              )}

              {onCheck && (
                <form className="answer-form" onSubmit={check}>
                  <input
                    aria-label={`Your answer to question ${question.number}`}
                    placeholder="Your answer"
                    maxLength={500}
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                  />
                  <button type="submit" className="primary" disabled={checking || !answer.trim()}>
                    {checking ? "Checking…" : "Check my answer"}
                  </button>
                </form>
              )}
              {shownResult && (
                <div
                  className={`check-result ${shownResult.correct ? "correct" : "not-yet"}`}
                  role="status"
                >
                  <Markdown text={shownResult.feedback} />
                </div>
              )}
              {error && (
                <div className="notice" role="alert">
                  {error}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}
