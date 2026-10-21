from dataclasses import dataclass
from typing import Literal

from prof_ai.chat.models import Usage

Provider = Literal["foundry", "ollama"]


class UnknownModelError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelProfile:
    deployment: str
    context_window: int
    max_output_tokens: int
    input_usd_per_m: float
    cached_input_usd_per_m: float
    output_usd_per_m: float
    provider: Provider = "foundry"
    label: str = ""
    # Only approved models may see a student's conversation (ADR 0005: data location, a DPA,
    # a content filter, and a pass on `prof eval dilution`).
    approved_for_student_conversations: bool = False
    notes: str = ""

    def cost_micro_usd(self, usage: Usage) -> int:
        # Dollars per million tokens is the same number as micro-dollars per token.
        uncached = max(usage.input_tokens - usage.cached_input_tokens, 0)
        return round(
            uncached * self.input_usd_per_m
            + usage.cached_input_tokens * self.cached_input_usd_per_m
            + usage.output_tokens * self.output_usd_per_m
        )


# Prices checked against the October 2026 bill (Global Standard, short context). Cached input
# hasn't been billed yet; 10% of input is assumed until it is.
LUNA = ModelProfile(
    deployment="gpt-5.6-luna",
    context_window=922_000,
    max_output_tokens=1_500,
    input_usd_per_m=0.20,
    cached_input_usd_per_m=0.02,
    output_usd_per_m=1.20,
    label="Luna (GPT-5.6, Microsoft Foundry)",
    approved_for_student_conversations=True,
    notes=(
        "The default. Hosted by Microsoft with content filters. Dilution eval: every scenario "
        "passed 3/3 with lessons up to 40k tokens (2026-10-19)."
    ),
)

# Ollama Cloud's peak prices from ollama.com/pricing on 2026-10-21. US-hosted, no DPA and no
# content filter, so not approved for student conversations.
OLLAMA_NOTES = (
    "Ollama Cloud, US-hosted, no content filter: for your own test chats, not students. "
    "Not evaluated yet."
)
GLM_FLASH = ModelProfile(
    deployment="glm-5.3-flash",
    context_window=1_048_576,
    max_output_tokens=1_500,
    input_usd_per_m=0.15,
    cached_input_usd_per_m=0.03,
    output_usd_per_m=0.50,
    provider="ollama",
    label="GLM-5.3 Flash (Ollama Cloud)",
    notes=OLLAMA_NOTES,
)
DEEPSEEK_FLASH = ModelProfile(
    deployment="deepseek-v4.1-flash",
    context_window=1_048_576,
    max_output_tokens=1_500,
    input_usd_per_m=0.30,
    cached_input_usd_per_m=0.006,
    output_usd_per_m=1.20,
    provider="ollama",
    label="DeepSeek V4.1 Flash (Ollama Cloud)",
    notes=OLLAMA_NOTES,
)

MODEL_PROFILES = {profile.deployment: profile for profile in (LUNA, GLM_FLASH, DEEPSEEK_FLASH)}


def model_profile(deployment: str) -> ModelProfile:
    try:
        return MODEL_PROFILES[deployment]
    except KeyError:
        raise UnknownModelError(
            f"No model profile for deployment {deployment!r}; add one to model_profiles.py."
        ) from None
