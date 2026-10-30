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


def test_section_names_are_canonical():
    text = "INTRODUCTION\n\nSome text here.\n\n5 EVALUATION SETTING\n\nMore text.\n\nACKNOWLEDGEMENTS\n\nThanks."
    assert titles(split_sections(text)) == ["Introduction", "Evaluation Setting", "Acknowledgments"]


def test_long_text_after_a_tail_heading_becomes_appendix():
    para = " ".join(["word"] * 200)
    text = "\n\n".join(["1 Introduction", "Intro text.", "Limitations", para, para, para])
    secs = split_sections(text)
    assert titles(secs) == ["Introduction", "Limitations", "Appendix"]
    assert len(secs[1][1].split()) == 200          # first paragraph keeps the label
    assert len(secs[2][1].split()) == 400          # the rest is appendix


def test_short_tail_section_is_unchanged():
    text = "1 Introduction\n\nIntro text.\n\nLimitations\n\nOur study has a small sample.\n\n2 Method\n\nWe do things."
    assert titles(split_sections(text)) == ["Introduction", "Limitations", "Method"]


def test_numbered_list_items_are_not_headings():
    from src.processing.sections import _heading_of
    assert _heading_of("1. Y=GEMM(X, W) - the product between the input,") is None
    assert _heading_of("2. Use a smaller learning rate first;") is None
    assert _heading_of("3.2 Decoupled RL Training") is not None
    assert _heading_of("4 Experiments") is not None


def test_math_lines_are_not_headings():
    from src.processing.sections import _heading_of
    assert _heading_of("5 Hence D \u2265 h2/\u03c32") is None
    assert _heading_of("2 Let x \u2208 R be a vector") is None
    assert _heading_of("5 Hence a stable result") is not None  # same shape, no maths symbol


def test_long_text_after_conclusion_becomes_appendix():
    para = " ".join(["word"] * 300)
    text = "\n\n".join(["1 Introduction", "Intro text.", "6 Conclusion", para, para, para])
    secs = split_sections(text)
    assert titles(secs) == ["Introduction", "Conclusion", "Appendix"]
    assert len(secs[1][1].split()) == 600   # conclusions may run longer than other closing sections
    assert len(secs[2][1].split()) == 300


def test_conclusion_and_limitations_title_is_also_capped():
    para = " ".join(["word"] * 300)
    text = "\n\n".join(["Intro text first.", "7 Conclusion and Limitations", para, para, para])
    assert titles(split_sections(text)) == ["Preamble", "Conclusion and Limitations", "Appendix"]


def test_short_conclusion_is_unchanged():
    text = "1 Introduction\n\nIntro text.\n\n6 Conclusion\n\nWe showed it works."
    assert titles(split_sections(text)) == ["Introduction", "Conclusion"]