from src.processing.sections import split_sections


def titles(sections):
    return [t for t, _ in sections]


def test_numbered_and_known_headings():
    text = "\n\n".join(
        [
            "Abstract We study retrieval quality in detail.",
            "1 Introduction",
            "Retrieval matters because answers depend on evidence.",
            "3.2 Decoupled RL Training",
            "We train with two signals.",
            "Conclusion",
            "We summarise the work.",
        ]
    )
    secs = split_sections(text)
    assert titles(secs) == ["Abstract", "Introduction", "Decoupled RL Training", "Conclusion"]
    assert secs[0][1].startswith("We study retrieval")  # the glued text is kept


def test_numbered_heading_glued_to_text():
    text = "Abstract Short abstract text.\n\n6 Conclusion This work introduces a verifier."
    secs = split_sections(text)
    assert titles(secs) == ["Abstract", "Conclusion"]
    assert secs[1][1] == "This work introduces a verifier."


def test_body_sentence_starting_with_results_is_not_a_heading():
    text = "Abstract Intro text here.\n\nResults show that the method works well on most tasks."
    secs = split_sections(text)
    assert titles(secs) == ["Abstract"]
    assert "Results show" in secs[0][1]


def test_no_headings_becomes_single_body_section():
    secs = split_sections("Just a paragraph of plain text.\n\nAnd another paragraph.")
    assert titles(secs) == ["Body"]


def test_text_before_first_heading_is_preamble():
    secs = split_sections("Some opening text.\n\n1 Introduction\n\nMore text.")
    assert titles(secs) == ["Preamble", "Introduction"]


def test_decimal_numbers_are_not_section_numbers():
    from src.processing.sections import _heading_of
    assert _heading_of("0.09 Gain") is None
    assert _heading_of("0.72 Score") is None
    assert _heading_of("3.2 Decoupled RL Training") is not None