import pytest

from prof_ai.chat.prompts import BASE_PROMPT, build_system_prompt
from prof_ai.profiles.store import (
    MAX_PROFILE_BYTES,
    PROFILES_CONTAINER,
    InvalidProfileError,
    ProfileFile,
)


def test_profiles_live_in_a_folder_per_user(harness):
    harness.profiles.put("alex", ProfileFile.PROFILE, "Alex, Year 9, likes football.")
    harness.profiles.put("sam", ProfileFile.TEACHING_STYLE, "Socratic questions.")
    assert harness.blobs.blobs[(PROFILES_CONTAINER, "alex/profile.md")] == (
        b"Alex, Year 9, likes football."
    )
    assert (PROFILES_CONTAINER, "sam/teaching-style.md") in harness.blobs.blobs


def test_student_prompt_layers_base_then_tutor_style_then_profile(harness):
    harness.profiles.put("sam", ProfileFile.TEACHING_STYLE, "Use Socratic questions.")
    harness.profiles.put("alex", ProfileFile.PROFILE, "Alex, Year 9.")
    prompt = build_system_prompt(harness.users.get("alex"), harness.profiles)
    assert prompt.startswith(BASE_PROMPT)
    assert prompt.index("Use Socratic questions.") < prompt.index("Alex, Year 9.")


def test_students_of_different_tutors_get_different_prompts(harness):
    harness.profiles.put("sam", ProfileFile.TEACHING_STYLE, "Sam style: worked examples.")
    harness.profiles.put("punjy", ProfileFile.TEACHING_STYLE, "Punjy style: quick quizzes.")
    alex = build_system_prompt(harness.users.get("alex"), harness.profiles)
    bea = build_system_prompt(harness.users.get("bea"), harness.profiles)
    assert "Sam style" in alex and "Punjy style" not in alex
    assert "Punjy style" in bea and "Sam style" not in bea


def test_tutor_gets_their_own_teaching_style(harness):
    harness.profiles.put("sam", ProfileFile.TEACHING_STYLE, "Sam style.")
    harness.profiles.put("sam", ProfileFile.PROFILE, "Sam is testing the tutor.")
    prompt = build_system_prompt(harness.users.get("sam"), harness.profiles)
    assert "Sam style." in prompt
    assert "Sam is testing the tutor." in prompt


def test_missing_profiles_leave_just_the_base_prompt(harness):
    assert build_system_prompt(harness.users.get("alex"), harness.profiles) == BASE_PROMPT


def test_another_users_profile_never_leaks_in(harness):
    harness.profiles.put("bea", ProfileFile.PROFILE, "Bea's private notes.")
    assert "Bea" not in build_system_prompt(harness.users.get("alex"), harness.profiles)


@pytest.mark.parametrize("text", ["", "   ", "x" * (MAX_PROFILE_BYTES + 1)])
def test_empty_or_oversized_profiles_are_refused(harness, text):
    with pytest.raises(InvalidProfileError):
        harness.profiles.put("alex", ProfileFile.PROFILE, text)
    assert not harness.blobs.blobs
