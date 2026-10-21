from types import SimpleNamespace

import httpx2
import openai
import pytest
from fastapi.testclient import TestClient

from prof_ai.chat.context import check_budget
from prof_ai.chat.model import (
    ContentFilteredError,
    ModelRateLimitedError,
    ModelUnavailableError,
    OpenAIChatModel,
)
from prof_ai.chat.model_profiles import GLM_FLASH, LUNA, MODEL_PROFILES
from prof_ai.chat.models import PromptMessage, Usage
from prof_ai.chat.service import AvailableModel, ChatService
from prof_ai.config import load_settings
from prof_ai.main import create_app
from tests.lessons.conftest import RATIOS, LessonHarness
from tests.tutor_chat.conftest import FIXED_NOW, PRODUCTION, FakeModel, parse_events


class ProvidersHarness(LessonHarness):
    """Luna by default, plus a fake unapproved GLM Flash."""

    def __init__(self) -> None:
        super().__init__()
        self.glm = FakeModel()
        self.glm.reply = ["GLM ", "here."]
        self.service = ChatService(
            self.model,
            self.store,
            self.profiles,
            self.limits,
            clock=lambda: FIXED_NOW,
            extra_models=[AvailableModel(GLM_FLASH, self.glm)],
        )
        self.client = TestClient(
            create_app(PRODUCTION, user_repository=self.users, chat_service=self.service)
        )

    def create_with(self, student_id: str, model: str | None, actor: str = "sam"):
        body = {"lesson": RATIOS, "licence_confirmed": True, "model": model}
        return self.client.post(self.chats_url(student_id), json=body, headers=self.as_user(actor))

    def patch(self, student_id: str, chat_id: str, body: dict, actor: str = "sam"):
        return self.client.patch(
            f"{self.chats_url(student_id)}/{chat_id}", json=body, headers=self.as_user(actor)
        )

    def prefer(self, model: str | None, actor: str = "sam"):
        return self.client.put(
            "/api/models/preferred", json={"model": model}, headers=self.as_user(actor)
        )


@pytest.fixture
def h() -> ProvidersHarness:
    return ProvidersHarness()


def chunk(content=None, finish_reason=None, usage=None):
    choices = (
        []
        if content is None and finish_reason is None
        else [SimpleNamespace(delta=SimpleNamespace(content=content), finish_reason=finish_reason)]
    )
    return SimpleNamespace(choices=choices, usage=usage)


class FakeCompletions:
    def __init__(self, chunks=(), error: Exception | None = None):
        self.chunks = chunks
        self.error = error
        self.kwargs: dict = {}

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return iter(self.chunks)


def adapter(completions: FakeCompletions, cap_param: str = "max_tokens") -> OpenAIChatModel:
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return OpenAIChatModel(client, "glm-5.3-flash", cap_param)


def api_error(cls, status: int, code: str | None = None):
    response = httpx2.Response(status, request=httpx2.Request("POST", "https://example.test"))
    return cls("error", response=response, body={"code": code} if code else None)


MESSAGES = [PromptMessage(role="user", content="hi")]


@pytest.mark.parametrize("cap_param", ["max_tokens", "max_completion_tokens"])
def test_the_adapter_streams_text_then_usage_with_the_providers_output_cap(cap_param):
    usage = SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=20,
        prompt_tokens_details=SimpleNamespace(cached_tokens=40),
    )
    completions = FakeCompletions([chunk("Hel"), chunk("lo"), chunk(usage=usage)])
    items = list(adapter(completions, cap_param).stream(MESSAGES, 1_500))
    assert items == [
        "Hel",
        "lo",
        Usage(input_tokens=100, output_tokens=20, cached_input_tokens=40),
    ]
    assert completions.kwargs[cap_param] == 1_500
    assert completions.kwargs["model"] == "glm-5.3-flash"
    assert completions.kwargs["stream_options"] == {"include_usage": True}


def test_the_adapter_reads_usage_without_cache_details():
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=2, prompt_tokens_details=None)
    [item] = adapter(FakeCompletions([chunk(usage=usage)])).stream(MESSAGES, 100)
    assert item == Usage(input_tokens=10, output_tokens=2)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (api_error(openai.RateLimitError, 429), ModelRateLimitedError),
        (api_error(openai.AuthenticationError, 401), ModelUnavailableError),
        (api_error(openai.BadRequestError, 400, "content_filter"), ContentFilteredError),
        (api_error(openai.BadRequestError, 400), ModelUnavailableError),
    ],
)
def test_the_adapter_maps_provider_errors(error, expected):
    with pytest.raises(expected):
        list(adapter(FakeCompletions(error=error)).stream(MESSAGES, 100))


def test_a_content_filter_finish_is_a_filtered_reply():
    with pytest.raises(ContentFilteredError):
        list(adapter(FakeCompletions([chunk(finish_reason="content_filter")])).stream(MESSAGES, 1))


def test_every_registered_model_passes_the_startup_check():
    for profile in MODEL_PROFILES.values():
        check_budget(profile, 50_000 if profile.provider == "foundry" else None)


def test_only_luna_is_approved_for_student_conversations():
    approved = [
        p.deployment for p in MODEL_PROFILES.values() if p.approved_for_student_conversations
    ]
    assert approved == [LUNA.deployment]


def test_tutors_see_each_model_with_its_cost_and_approval(h):
    body = h.client.get("/api/models", headers=h.as_user("sam")).json()
    assert body["default"] == LUNA.deployment and body["preferred"] is None
    models = {m["id"]: m for m in body["models"]}
    assert set(models) == {LUNA.deployment, GLM_FLASH.deployment}
    assert models[LUNA.deployment]["approved_for_student_conversations"] is True
    assert models[GLM_FLASH.deployment]["approved_for_student_conversations"] is False
    assert models[GLM_FLASH.deployment]["output_usd_per_m"] == 0.50
    expected = (6_000 * 0.15 + 300 * 0.50) / 1_000_000
    assert models[GLM_FLASH.deployment]["typical_message_usd"] == pytest.approx(expected)


def test_the_models_api_is_for_signed_in_tutors_only(h):
    assert h.client.get("/api/models").status_code == 401
    assert h.client.get("/api/models", headers=h.as_user("alex")).status_code == 403
    assert h.prefer(GLM_FLASH.deployment, actor="alex").status_code == 403


def test_an_unapproved_model_cannot_be_set_on_a_students_chat(h):
    response = h.create_with("alex", GLM_FLASH.deployment)
    assert response.status_code == 400
    assert "isn't approved for student conversations" in response.json()["detail"]
    chat_id = h.create_with("alex", None).json()["id"]
    assert h.patch("alex", chat_id, {"model": GLM_FLASH.deployment}).status_code == 400
    assert h.create_with("alex", "no-such-model").status_code == 400


def test_a_students_chat_runs_on_its_approved_model(h):
    chat = h.create_with("alex", LUNA.deployment).json()
    assert chat["model"] == LUNA.deployment
    h.send("alex", chat["id"], "help")
    assert len(h.model.calls) == 1 and h.glm.calls == []


def test_a_tutor_can_try_an_unapproved_model_in_their_own_lesson(h):
    chat = h.create_with("sam", GLM_FLASH.deployment).json()
    events = parse_events(h.send("sam", chat["id"], "@AI hello").text)
    assert ("delta", {"text": "GLM "}) in events
    assert h.model.calls == []
    day = FIXED_NOW.date()
    assert h.store.cost_used("sam", day) == GLM_FLASH.cost_micro_usd(h.glm.usage)


def test_a_tutors_test_chat_uses_their_preferred_model_and_the_change_is_audited(h):
    assert h.prefer(GLM_FLASH.deployment).json()["preferred"] == GLM_FLASH.deployment
    assert h.users.events[-1].action == "preferred_model_changed"
    chat_id = h.service.create_chat(h.users.get("sam"), h.users.get("sam")).id
    h.send("sam", chat_id, "hello")
    assert len(h.glm.calls) == 1 and h.model.calls == []
    assert h.prefer("no-such-model").status_code == 400
    assert h.prefer(None).json()["preferred"] is None


def test_a_students_chat_never_runs_an_unapproved_model(h):
    chat_id = h.create_with("alex", None).json()["id"]
    h.store.update_conversation(
        "alex", chat_id, lambda c: setattr(c, "model", GLM_FLASH.deployment)
    )
    assert h.send("alex", chat_id, "help").status_code == 503
    assert h.glm.calls == [] and h.model.calls == []


def test_the_tutors_preferred_model_never_reaches_a_students_chat(h):
    h.prefer(GLM_FLASH.deployment)
    chat_id = h.create_with("alex", None).json()["id"]
    h.send("alex", chat_id, "help")
    assert h.glm.calls == [] and len(h.model.calls) == 1


def test_changing_a_chats_model_is_audited(h):
    chat_id = h.create_with("sam", None).json()["id"]
    response = h.patch("sam", chat_id, {"model": GLM_FLASH.deployment})
    assert response.status_code == 200 and response.json()["model"] == GLM_FLASH.deployment
    assert h.users.events[-1].action == "chat_model_changed"
    assert h.patch("sam", chat_id, {}).status_code == 400


def test_an_unresolved_key_vault_reference_counts_as_no_key(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "@Microsoft.KeyVault(SecretUri=https://kv/secrets/x/)")
    assert load_settings().ollama_api_key == ""
    monkeypatch.setenv("OLLAMA_API_KEY", " real-looking-key ")
    assert load_settings().ollama_api_key == "real-looking-key"
