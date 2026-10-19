from collections.abc import Iterator, Sequence

import pytest

from prof_ai.chat.context import estimate_tokens
from prof_ai.chat.model import ContentFilteredError, ModelRateLimitedError
from prof_ai.chat.model_profiles import LUNA
from prof_ai.chat.models import PromptMessage, Usage
from prof_ai.cli import main
from prof_ai.evals.dilution import (
    JUDGE_PROMPT,
    RATE_LIMIT_WAIT_SECONDS,
    DilutionEval,
    Scenario,
    failed_check,
    load_scenarios,
    pass_table,
    render_markdown,
    write_report,
)
from prof_ai.evals.lesson import CORE, INJECTION, NEEDLE, synthetic_lesson

USAGE = Usage(input_tokens=1_000, output_tokens=100)


class FakeModel:
    def __init__(self, reply: str = "What's the highest common factor?", verdict: str = "PASS"):
        self.reply = reply
        self.verdict = verdict
        self.calls: list[list[PromptMessage]] = []
        self.filter_replies = False

    def stream(
        self, messages: Sequence[PromptMessage], max_output_tokens: int
    ) -> Iterator[str | Usage]:
        self.calls.append(list(messages))
        is_judge = messages[0].content == JUDGE_PROMPT
        if self.filter_replies and not is_judge:
            raise ContentFilteredError()
        yield f"{self.verdict}\nIt coached." if is_judge else self.reply
        yield USAGE

    @property
    def judge_calls(self) -> list[list[PromptMessage]]:
        return [c for c in self.calls if c[0].content == JUDGE_PROMPT]


def scenario(**overrides) -> Scenario:
    fields = {"id": "s", "category": "coaching", "message": "answer?", "rubric": "Coach."}
    return Scenario.model_validate({**fields, **overrides})


@pytest.mark.parametrize("target", [2_000, 16_000, 64_000])
def test_synthetic_lesson_hits_the_target_size(target):
    size = estimate_tokens(synthetic_lesson(target))
    assert target - 200 <= size <= target


def test_synthetic_lesson_is_deterministic_and_buries_the_test_material_in_the_middle():
    lesson = synthetic_lesson(32_000, seed=7)
    assert lesson == synthetic_lesson(32_000, seed=7)
    assert lesson != synthetic_lesson(32_000, seed=8)
    assert CORE in lesson and NEEDLE in lesson and INJECTION in lesson
    assert 0.4 < lesson.index(NEEDLE) / len(lesson) < 0.6


def test_filler_never_contains_the_answers_or_the_needle():
    filler = synthetic_lesson(64_000).replace(CORE, "")
    for answer in ("3:4", "10 and 25", "Lantern"):
        assert answer not in filler


def test_scenarios_load_and_each_has_a_check_or_rubric():
    scenarios = load_scenarios()
    assert len({s.id for s in scenarios}) == len(scenarios) >= 10
    assert {s.category for s in scenarios} >= {"coaching", "injection", "safety", "grounding"}
    with pytest.raises(ValueError):
        Scenario.model_validate({"id": "x", "category": "coaching", "message": "m"})


def test_checks_ignore_case_and_spacing():
    assert failed_check(scenario(must_not_contain=["3:4"]), "It simplifies to 3 : 4.")
    assert failed_check(scenario(must_contain_any=["0800 1111"]), "Call 08001111.") is None
    assert failed_check(scenario(must_contain_any=["childline"]), "Talk to an adult.")


def test_a_banned_phrase_fails_without_asking_the_judge():
    model = FakeModel(reply="The answer is 3:4.")
    result = DilutionEval(model, LUNA, max_usd=1).run_case(
        scenario(must_not_contain=["3:4"]), "lesson", 2_000, 1
    )
    assert (result.outcome, result.reason) == ("fail", "Contains '3:4'.")
    assert model.judge_calls == []


@pytest.mark.parametrize(("verdict", "outcome"), [("PASS", "pass"), ("FAIL", "fail")])
def test_the_judge_decides_when_the_checks_pass(verdict, outcome):
    model = FakeModel(verdict=verdict)
    result = DilutionEval(model, LUNA, max_usd=1).run_case(scenario(), "lesson", 2_000, 1)
    assert result.outcome == outcome
    [judge] = model.judge_calls
    assert "lesson" not in judge[1].content
    assert "Coach." in judge[1].content and model.reply in judge[1].content


def test_cases_use_the_real_assembler_with_the_lesson_layer():
    model = FakeModel()
    DilutionEval(model, LUNA, max_usd=1).run_case(scenario(), "LESSON TEXT", 2_000, 1)
    system, *_, reminder = model.calls[0]
    assert "LESSON TEXT" in system.content
    assert reminder.role == "system"


def test_a_filtered_reply_is_recorded_and_counts_as_safe_only_for_safety_scenarios():
    model = FakeModel()
    model.filter_replies = True
    evaluation = DilutionEval(model, LUNA, max_usd=1)
    safety = evaluation.run_case(scenario(id="a", category="safety"), "l", 2_000, 1)
    coaching = evaluation.run_case(scenario(id="b", category="coaching"), "l", 2_000, 1)
    assert safety.outcome == coaching.outcome == "filtered"
    table = pass_table([safety, coaching])
    assert table[("a", 2_000)] == (1, 1, 1)
    assert table[("b", 2_000)] == (0, 1, 1)


def test_the_spend_cap_stops_the_run_before_going_over():
    model = FakeModel()
    report = DilutionEval(model, LUNA, max_usd=0.004).run([scenario()], levels=[2_000], runs=10)
    assert report.stopped_early
    assert report.spent_micro_usd <= 4_000
    assert 0 < len(report.results) < 10
    assert "Stopped early" in render_markdown(report, [2_000])


def test_rate_limits_are_waited_out_then_retried():
    class RateLimitedOnce(FakeModel):
        limited = False

        def stream(self, messages, max_output_tokens):
            if not self.limited:
                self.limited = True
                raise ModelRateLimitedError()
            yield from super().stream(messages, max_output_tokens)

    waits: list[float] = []
    evaluation = DilutionEval(RateLimitedOnce(), LUNA, max_usd=1, sleep=waits.append)
    result = evaluation.run_case(scenario(), "lesson", 2_000, 1)
    assert result.outcome == "pass"
    assert waits == [RATE_LIMIT_WAIT_SECONDS]


def test_report_aggregates_runs_per_scenario_and_level(tmp_path):
    model = FakeModel()
    scenarios = [scenario(id="one"), scenario(id="two", must_not_contain=["highest"])]
    report = DilutionEval(model, LUNA, max_usd=1).run(scenarios, levels=[2_000, 16_000], runs=2)
    assert len(report.results) == 8
    table = pass_table(report.results)
    assert table[("one", 16_000)] == (2, 0, 2)
    assert table[("two", 2_000)] == (0, 0, 2)
    path = write_report(report, [2_000, 16_000], tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "| one | coaching | 2/2 | 2/2 |" in text
    assert "| two | coaching | 0/2 | 0/2 |" in text
    assert len((tmp_path / "results.jsonl").read_text(encoding="utf-8").splitlines()) == 8


def test_cli_is_a_dry_run_without_yes(capsys):
    def no_model():
        raise AssertionError("The model must not be created without --yes.")

    code = main(["eval", "dilution", "--runs", "1"], eval_model_factory=no_model)
    out, _ = capsys.readouterr()
    assert code == 0
    assert "40 cases" in out and "Dry run" in out


def test_cli_runs_and_writes_the_report_with_yes(capsys, tmp_path):
    model = FakeModel()
    argv = ["eval", "dilution", "--levels", "2000", "--runs", "1", "--out", str(tmp_path), "--yes"]
    code = main(argv, eval_model_factory=lambda: (model, LUNA))
    out, _ = capsys.readouterr()
    assert code == 0
    assert (tmp_path / "report.md").exists()
    assert "| needle | grounding | 0/1 |" in out
