from prof_ai.chat.prompts import BASE_PROMPT


def test_prof_ai_is_asked_for_markdown_with_latex_maths():
    assert "Write in simple Markdown" in BASE_PROMPT
    assert "LaTeX between single dollar signs" in BASE_PROMPT


def test_prof_ai_still_avoids_html_and_dollar_signs_for_money():
    assert "Don't use HTML" in BASE_PROMPT
    assert "never with a dollar sign" in BASE_PROMPT
