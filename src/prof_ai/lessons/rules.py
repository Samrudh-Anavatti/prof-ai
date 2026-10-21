from prof_ai.chat.context import LAYER_CAPS, Layer, estimate_tokens
from prof_ai.chat.models import Lesson, Question, WorkedExample

MAX_TITLE_CHARS = 120
MAX_TOPICS = 20
MAX_TOPIC_CHARS = 120
MAX_NOTES_CHARS = 2_000


class InvalidLessonError(ValueError):
    pass


def render_lesson(lesson: Lesson) -> str:
    parts = [f"### {lesson.title}"]
    if lesson.topics:
        parts.append("Topics: " + "; ".join(lesson.topics))
    if lesson.notes:
        parts.append(f"What the tutor wants this chat to focus on:\n{lesson.notes}")
    if lesson.material:
        parts.append(f"Lesson material:\n\n{lesson.material}")
    if lesson.worked_examples:
        examples = "\n\n".join(
            f"#### {example.title or 'Example'}\n{example.text}"
            for example in lesson.worked_examples
        )
        parts.append(f"Worked examples:\n\n{examples}")
    if lesson.questions:
        # Answers stay out of the lesson layer: the model sees them only to check one answer.
        questions = "\n".join(f"{q.number}. {q.text}" for q in lesson.questions)
        parts.append(f"Questions for the student:\n{questions}")
    return "\n\n".join(parts)


def lesson_tokens(lesson: Lesson) -> int:
    return estimate_tokens(render_lesson(lesson))


def validate_lesson(lesson: Lesson, licence_confirmed: bool) -> Lesson:
    """Tidy a lesson and enforce ADR 0005's write-time cap on the lesson layer."""
    lesson = lesson.model_copy(
        update={
            "title": lesson.title.strip(),
            "topics": [t.strip() for t in lesson.topics if t.strip()],
            "notes": lesson.notes.strip(),
            "material": lesson.material.strip(),
            "worked_examples": [
                WorkedExample(title=e.title.strip(), text=e.text.strip())
                for e in lesson.worked_examples
                if e.text.strip()
            ],
            "questions": [
                Question(
                    number=q.number.strip(),
                    text=q.text.strip(),
                    answer=(q.answer or "").strip() or None,
                )
                for q in lesson.questions
                if q.text.strip()
            ],
        }
    )
    if not lesson.title:
        raise InvalidLessonError("Give the lesson a title.")
    if len(lesson.title) > MAX_TITLE_CHARS:
        raise InvalidLessonError(f"Keep the title under {MAX_TITLE_CHARS} characters.")
    if len(lesson.topics) > MAX_TOPICS or any(len(t) > MAX_TOPIC_CHARS for t in lesson.topics):
        raise InvalidLessonError(
            f"Use at most {MAX_TOPICS} topics of up to {MAX_TOPIC_CHARS} characters each."
        )
    if len(lesson.notes) > MAX_NOTES_CHARS:
        raise InvalidLessonError(f"Keep the notes under {MAX_NOTES_CHARS} characters.")
    if (lesson.material or lesson.worked_examples or lesson.questions) and not licence_confirmed:
        raise InvalidLessonError("Confirm you're allowed to use this material with your student.")
    tokens = lesson_tokens(lesson)
    cap = LAYER_CAPS[Layer.LESSON]
    if tokens > cap:
        raise InvalidLessonError(
            f"The lesson is about {tokens:,} tokens; the limit is {cap:,}. "
            "Remove some pages or text."
        )
    return lesson
