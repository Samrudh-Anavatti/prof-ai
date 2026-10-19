from dataclasses import dataclass

from prof_ai.chat.models import Usage


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
    max_output_tokens=4_000,
    input_usd_per_m=0.20,
    cached_input_usd_per_m=0.02,
    output_usd_per_m=1.20,
)

MODEL_PROFILES = {profile.deployment: profile for profile in (LUNA,)}


def model_profile(deployment: str) -> ModelProfile:
    try:
        return MODEL_PROFILES[deployment]
    except KeyError:
        raise UnknownModelError(
            f"No model profile for deployment {deployment!r}; add one to model_profiles.py."
        ) from None
