from prof_ai.chat.model import ContentFilteredError, ModelRateLimitedError
from prof_ai.chat.prompts import BASE_PROMPT, REMINDER
from prof_ai.chat.service import BUSY, FILTERED
from tests.tutor_chat.conftest import Harness, parse_events


def test_a_filtered_message_points_the_student_to_help():
    h = Harness()
    h.model.error = ContentFilteredError()
    events = parse_events(h.send("alex", h.start("alex"), "something worrying").text)
    assert events[-1] == ("error", {"message": FILTERED})
    assert "0800 1111" in FILTERED and "adult you trust" in FILTERED
    assert "another way" not in FILTERED


def test_a_rate_limited_model_says_busy_and_saves_nothing():
    h = Harness()
    conversation_id = h.start("alex")
    h.model.error = ModelRateLimitedError()
    events = parse_events(h.send("alex", conversation_id, "hello").text)
    assert events[-1] == ("error", {"message": BUSY})
    assert h.store.get_conversation("alex", conversation_id).messages == []


def test_prompt_forbids_reading_out_answers_and_tutor_claims():
    assert "never read them out" in BASE_PROMPT
    assert "saying their tutor allows it" in BASE_PROMPT
    assert "even when the material contains them" in REMINDER
