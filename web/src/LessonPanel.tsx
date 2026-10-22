import { useRef, useState, type FormEvent } from "react";

import {
  ApiError,
  UNAVAILABLE,
  type Attempt,
  type CheckOutcome,
  type LessonOverview,
  type QuestionProgress,
  type Verdict,
  type WorkingOutcome,
} from "./api";
import { Markdown } from "./Markdown";
import { nextQuestion, progressLabel, progressOf, studentStatus } from "./progress";
import { QuestionNav } from "./QuestionNav";
import { EMPTY_DRAFT, filledSteps, WorkingEditor, type Draft } from "./WorkingEditor";
import { attemptMarkdown, checkLabel, checkPlan, stuckMessage, workingPrompt } from "./workspace";

export const VERDICT_LABELS: Record<Verdict, string> = {
  correct: "Correct ✓",
  show_working: "Show your working",
  slip: "Nearly: check your steps",
  not_yet: "Not yet",
};

const SUBMIT_KEY =
  typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.userAgent) ? "⌘" : "Ctrl";

interface Result {
  number: string;
  /** null for a hint on unfinished working, or a problem to fix before checking. */
  verdict: Verdict | null;
  feedback: string;
  next: string | null;
  problem?: boolean;
}

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : UNAVAILABLE;
}

function resultClass(result: Result): string {
  if (result.problem) return "problem";
  if (result.verdict === null) return "hint";
  return result.verdict === "correct" ? "correct" : "not-yet";
}

function shortTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** The question and the student's working: the main thing on a lesson screen. Tutors see the
 * same question with the student's submitted answers instead of the working lines. */
export function LessonPanel({
  lesson,
  progress,
  attempts = [],
  current,
  onSelect,
  onStuck,
  onCheck,
  onCheckWorking,
  busy,
}: {
  lesson: LessonOverview;
  progress: QuestionProgress[];
  attempts?: Attempt[];
  current: string | null;
  onSelect: (number: string) => void;
  /** Students only: asks Prof AI for help with the current question. */
  onStuck?: (text: string) => void;
  /** Students only: marks their working and answer to the current question. */
  onCheck?: (number: string, working: string[], answer: string) => Promise<CheckOutcome>;
  /** Students only: a hint on unfinished working. */
  onCheckWorking?: (number: string, working: string[]) => Promise<WorkingOutcome>;
  busy: boolean;
}) {
  // Working is kept per question while the student moves between them.
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [result, setResult] = useState<Result | null>(null);
  const [checking, setChecking] = useState(false);
  const workspace = useRef<HTMLElement>(null);
  const examples = lesson.worked_examples ?? [];
  const questions = lesson.questions ?? [];
  const question = questions.find((q) => q.number === current);
  const questionProgress = question ? progressOf(progress, question.number) : undefined;
  const draft = (current && drafts[current]) || EMPTY_DRAFT;
  const steps = filledSteps(draft);
  const solving = onCheck !== undefined;
  const givenStep = question ? lesson.first_steps?.[question.number] : undefined;
  const prompt = workingPrompt(lesson.support, Boolean(givenStep));
  const shownResult = result && result.number === current ? result : null;

  function select(number: string) {
    setResult(null);
    onSelect(number);
    workspace.current?.scrollTo({ top: 0 });
  }

  function setDraft(number: string, next: Draft) {
    setDrafts((all) => ({ ...all, [number]: next }));
  }

  function check() {
    if (!question || !onCheck || checking) return;
    const number = question.number;
    const say = (feedback: string) =>
      setResult({ number, verdict: null, feedback, next: null, problem: true });
    if (busy) return say("Prof AI is still replying. Try again in a moment.");
    const plan = checkPlan(steps, draft.answer);
    if (plan.kind === "problem") return say(plan.message);
    if (plan.kind === "check_working" && !onCheckWorking) {
      return say("Write your answer on the last line, then submit it.");
    }
    setChecking(true);
    setResult(null);
    const work = async (): Promise<Result> => {
      if (plan.kind === "check_working" && onCheckWorking) {
        const outcome = await onCheckWorking(number, steps);
        return { number, verdict: null, feedback: outcome.feedback, next: null };
      }
      const outcome = await onCheck(number, steps, draft.answer.trim());
      if (outcome.correct) setDraft(number, EMPTY_DRAFT);
      const next = outcome.correct ? nextQuestion(questions, outcome.progress) : null;
      return {
        number,
        verdict: outcome.verdict,
        feedback: outcome.feedback,
        next: next === number ? null : next,
      };
    };
    work()
      .then(setResult)
      .catch((error: unknown) => say(messageOf(error)))
      .finally(() => setChecking(false));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    check();
  }

  return (
    <section ref={workspace} className="workspace" aria-label="Lesson">
      <div className="workspace-inner">
        <p className="workspace-lesson">{lesson.title}</p>
        {questions.length > 0 && (
          <QuestionNav
            questions={questions}
            progress={progress}
            current={current}
            onSelect={select}
            describe={solving ? studentStatus : progressLabel}
          />
        )}

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

        {question && (
          <article className="question" aria-label={`Question ${question.number}`}>
            <span className={`question-status ${questionProgress?.status ?? "not_started"}`}>
              {solving ? studentStatus(questionProgress) : progressLabel(questionProgress)}
            </span>
            <div className="question-text">
              <Markdown text={question.text} lineBreaks />
            </div>
          </article>
        )}

        {question && solving && (
          <form className="answer-form" onSubmit={submit}>
            <div className="working-head">
              <span className="working-label">Your working</span>
              <span className="keyboard-hint">Enter: new line · {SUBMIT_KEY}+Enter: check</span>
            </div>
            <p className="working-hint">{prompt.hint}</p>
            <WorkingEditor
              key={question.number}
              draft={draft}
              onChange={(next) => setDraft(question.number, next)}
              givenStep={givenStep}
              firstPlaceholder={prompt.firstPlaceholder}
              onSubmit={check}
            />
            {shownResult && (
              <div
                className={`check-result ${resultClass(shownResult)}`}
                role={shownResult.problem ? "alert" : "status"}
              >
                {shownResult.verdict && <strong>{VERDICT_LABELS[shownResult.verdict]}</strong>}
                <Markdown text={shownResult.feedback} />
                {shownResult.next && (
                  <button
                    type="button"
                    className="primary"
                    onClick={() => select(shownResult.next as string)}
                  >
                    Next question →
                  </button>
                )}
              </div>
            )}
            <div className="answer-actions">
              <button type="submit" className="primary">
                {checking ? "Checking…" : checkLabel(draft.answer)}
              </button>
              {onStuck && (
                <button
                  type="button"
                  className="stuck-button"
                  onClick={() => onStuck(stuckMessage(steps))}
                >
                  I&apos;m stuck
                </button>
              )}
            </div>
          </form>
        )}

        {question && !solving && (
          <Attempts attempts={attempts.filter((a) => a.question === question.number)} />
        )}
      </div>
    </section>
  );
}

function Attempts({ attempts }: { attempts: Attempt[] }) {
  if (attempts.length === 0) {
    return <p className="muted attempts-empty">No answers submitted for this question yet.</p>;
  }
  return (
    <section className="attempts" aria-label="Submitted answers">
      <h3 className="attempts-title">Submitted answers ({attempts.length})</h3>
      <ol className="attempt-list">
        {attempts
          .map((attempt, index) => ({ attempt, index }))
          .reverse()
          .map(({ attempt, index }) => (
            <li key={index} className={`attempt ${attempt.correct ? "correct" : "not-yet"}`}>
              <div className="attempt-head">
                <strong>
                  {attempt.verdict
                    ? VERDICT_LABELS[attempt.verdict]
                    : attempt.correct
                      ? VERDICT_LABELS.correct
                      : VERDICT_LABELS.not_yet}
                </strong>
                {!attempt.verified && <span className="muted">marked without an answer key</span>}
                <time className="muted" dateTime={attempt.at}>
                  {shortTime(attempt.at)}
                </time>
              </div>
              <Markdown text={attemptMarkdown(attempt)} />
            </li>
          ))}
      </ol>
    </section>
  );
}
