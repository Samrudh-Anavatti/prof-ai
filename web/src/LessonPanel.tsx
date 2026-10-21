import { useState, type FormEvent } from "react";

import {
  ApiError,
  UNAVAILABLE,
  type CheckOutcome,
  type LessonOverview,
  type QuestionProgress,
  type Verdict,
  type WorkingOutcome,
} from "./api";
import { Markdown } from "./Markdown";
import { doneCount, HELP_PROMPTS, nextQuestion, progressLabel, progressOf } from "./progress";
import { EMPTY_DRAFT, filledSteps, WorkingEditor, type Draft } from "./WorkingEditor";

export const VERDICT_LABELS: Record<Verdict, string> = {
  correct: "Correct ✓",
  show_working: "Show your working",
  slip: "Nearly: check your steps",
  not_yet: "Not yet",
};

interface Result {
  number: string;
  /** null for a hint on unfinished working. */
  verdict: Verdict | null;
  feedback: string;
  next: string | null;
}

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : UNAVAILABLE;
}

function resultClass(verdict: Verdict | null): string {
  if (verdict === null) return "hint";
  return verdict === "correct" ? "correct" : "not-yet";
}

/** Worked examples, the questions and the current question, above a lesson chat. */
export function LessonPanel({
  lesson,
  progress,
  current,
  onSelect,
  onHelp,
  onCheck,
  onCheckWorking,
  busy,
}: {
  lesson: LessonOverview;
  progress: QuestionProgress[];
  current: string | null;
  onSelect: (number: string) => void;
  /** Students only: asks Prof AI about the current question. */
  onHelp?: (text: string) => void;
  /** Students only: marks their working and final answer to the current question. */
  onCheck?: (number: string, working: string[], answer: string) => Promise<CheckOutcome>;
  /** Students only: a hint on unfinished working. */
  onCheckWorking?: (number: string, working: string[]) => Promise<WorkingOutcome>;
  busy: boolean;
}) {
  // Working is kept per question while the student moves between them.
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [result, setResult] = useState<Result | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const examples = lesson.worked_examples ?? [];
  const questions = lesson.questions ?? [];
  const question = questions.find((q) => q.number === current);
  const draft = (current && drafts[current]) || EMPTY_DRAFT;
  const steps = filledSteps(draft);
  const shownResult = result && result.number === current ? result : null;
  const firstStepHint =
    lesson.support === "step_by_step" ? "Step 1: write down what the question gives you" : "Step 1";

  function select(number: string) {
    setError(null);
    onSelect(number);
  }

  function setDraft(number: string, next: Draft) {
    setDrafts((all) => ({ ...all, [number]: next }));
  }

  async function run(work: () => Promise<Result>) {
    setChecking(true);
    setError(null);
    try {
      setResult(await work());
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setChecking(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!question || !onCheck || steps.length === 0 || !draft.answer.trim()) return;
    const number = question.number;
    void run(async () => {
      const outcome = await onCheck(number, steps, draft.answer.trim());
      if (outcome.correct) setDraft(number, EMPTY_DRAFT);
      const next = outcome.correct ? nextQuestion(questions, outcome.progress) : null;
      return {
        number,
        verdict: outcome.verdict,
        feedback: outcome.feedback,
        next: next === number ? null : next,
      };
    });
  }

  function checkSoFar() {
    if (!question || !onCheckWorking || steps.length === 0) return;
    const number = question.number;
    void run(async () => {
      const outcome = await onCheckWorking(number, steps);
      return { number, verdict: null, feedback: outcome.feedback, next: null };
    });
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
                <form className="answer-form" onSubmit={submit}>
                  <WorkingEditor
                    key={question.number}
                    draft={draft}
                    onChange={(next) => setDraft(question.number, next)}
                    firstStepHint={firstStepHint}
                  />
                  <div className="answer-actions">
                    {onCheckWorking && (
                      <button
                        type="button"
                        className="secondary"
                        disabled={checking || busy || steps.length === 0}
                        onClick={checkSoFar}
                      >
                        Check my working so far
                      </button>
                    )}
                    <button
                      type="submit"
                      className="primary"
                      disabled={checking || busy || steps.length === 0 || !draft.answer.trim()}
                    >
                      {checking ? "Checking…" : "Submit my answer"}
                    </button>
                  </div>
                </form>
              )}
              {shownResult && (
                <div className={`check-result ${resultClass(shownResult.verdict)}`} role="status">
                  {shownResult.verdict && <strong>{VERDICT_LABELS[shownResult.verdict]}</strong>}
                  <Markdown text={shownResult.feedback} />
                  {shownResult.next && (
                    <button
                      type="button"
                      className="primary"
                      onClick={() => select(shownResult.next as string)}
                    >
                      Next question
                    </button>
                  )}
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
