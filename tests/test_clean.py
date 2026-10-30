from src.processing.clean import (
    clean_block,
    clean_document,
    strip_control_chars,
    cut_references,
    drop_fragment_runs,
    drop_repeated_blocks,
    is_noise_block,
    is_toc_block,
    trim_front_matter,
)


BODIES = [
    "Alpha retrieval methods improve answer quality across many benchmark datasets.",
    "Beta chunking strategies change how much context each passage carries forward.",
    "Gamma embeddings map sentences into a space where similar meanings sit close.",
    "Delta rerankers reorder candidates using a slower but more accurate scorer.",
    "Epsilon evaluation needs a golden set of questions with reviewed answers.",
    "Zeta monitoring tracks latency and failure rates for every pipeline stage.",
]


def make_pages(n=6):
    pages = []
    for i in range(1, n + 1):
        pages.append(
            [
                "Journal of Testing 2026",  # running header
                BODIES[i - 1],              # unique body text
                str(i),                     # page number
            ]
        )
    return pages


def test_running_header_and_page_numbers_removed():
    cleaned = drop_repeated_blocks(make_pages())
    flat = [b for p in cleaned for b in p]
    assert not any("Journal of Testing" in b for b in flat)
    assert not any(b.strip().isdigit() for b in flat)
    assert len(flat) == 6  # only the six body blocks remain


def test_short_documents_keep_repeated_blocks():
    cleaned = drop_repeated_blocks(make_pages(2))
    assert any("Journal of Testing" in b for p in cleaned for b in p)


def test_arxiv_stamp_removed():
    pages = [["arXiv:2610.20582v1 [cs.CL] 14 Oct 2026", "Real content here."]]
    assert drop_repeated_blocks(pages) == [["Real content here."]]


def test_hyphenation_and_newlines_fixed():
    assert clean_block("informa-\ntion retrieval\nis fun") == "information retrieval is fun"


def test_ligatures_normalised():
    assert clean_block("e\ufb03cient \ufb01nal") == "efficient final"


def test_references_cut_when_late():
    text = "Intro. " * 100 + "\n\nReferences\n\n[1] Someone. A paper."
    out = cut_references(text)
    assert "Someone" not in out and out.startswith("Intro.")


def test_references_mention_early_is_ignored():
    text = "References\n\nThis early heading must not truncate. " + "Body. " * 200
    assert cut_references(text) == text


def test_clean_document_end_to_end():
    pages = make_pages()
    pages[-1].append("References")
    pages[-1].append("[1] A cited work.")
    text = clean_document(pages)
    assert "cited work" not in text
    assert "Alpha retrieval methods" in text
    assert "Journal of Testing" not in text


def test_front_matter_trimmed_before_abstract():
    pages = [
        ["A Paper Title", "Alice Smith 1,2 Bob Jones 3", "Abstract We study retrieval.", "1 Introduction"],
        ["More body text."],
    ]
    out = trim_front_matter(pages)
    assert out[0][0].startswith("Abstract")
    assert "Alice" not in " ".join(out[0])
    assert len(out) == 2


def test_no_abstract_leaves_pages_unchanged():
    pages = [["Title", "Some intro text."], ["More body text."]]
    assert trim_front_matter(pages) == pages


def test_chart_axis_text_is_noise():
    axis = "0.09 Gain 0.72 0.78 0.84 0.90 Score Graded Binary 0 100 200 Training Step"
    assert is_noise_block(axis)


def test_real_sentences_and_short_blocks_are_kept():
    assert not is_noise_block("We train the verifier with two complementary reward signals.")
    assert not is_noise_block("Figure 3")  # short blocks are always kept
    assert not is_noise_block("The model reaches 90.2% accuracy on 5 of 6 benchmarks (see Table 2).")


def test_clean_document_drops_chart_text_between_sections():
    pages = [
        [
            "Abstract We study retrieval quality in some detail here.",
            "0.09 Gain 0.72 0.78 0.84 0.90 Score Graded Binary 0 100 200 Training Step",
            "1 Introduction",
            "Retrieval matters because answers depend on evidence found.",
        ]
    ]
    text = clean_document(pages)
    assert "Graded Binary" not in text
    assert "We study retrieval quality" in text and "Retrieval matters" in text


def test_chart_block_with_many_label_words_is_caught_by_number_ratio():
    block = ("0.09 Gain 0.72 0.78 0.84 0.90 Score Graded Binary Single Obj. Two Obj. "
             "Counting Colors Position 0.12 0.45 0.88")
    assert is_noise_block(block)


def test_result_sentences_and_citation_paragraphs_are_kept():
    results = ("On GenEval our model improves from 0.72 to 0.84, while on DPG it reaches "
               "85.3 compared with 81.1 for the baseline method.")
    cites = ("Multimodal models have progressed quickly (Cao et al., 2025; Seedream et al., "
             "2025; Chen et al., 2026), producing visually convincing images.")
    assert not is_noise_block(results)
    assert not is_noise_block(cites)


def test_run_of_tiny_fragments_is_dropped():
    blocks = ["0.09", "Gain", "Score", "Binary", "0 100 200",
              "A real sentence long enough to count as prose here."]
    dropped = []
    kept = drop_fragment_runs(blocks, dropped=dropped)
    assert kept == ["A real sentence long enough to count as prose here."]
    assert len(dropped) == 5


def test_short_run_of_fragments_is_kept():
    blocks = ["Gain", "Score", "A real sentence long enough to count as prose here."]
    assert drop_fragment_runs(blocks) == blocks


def test_headings_are_not_fragments():
    blocks = ["Introduction", "Conclusion", "1 Introduction", "2 Method",
              "Prose line that is long enough to be a normal paragraph."]
    assert drop_fragment_runs(blocks) == blocks


def test_clean_document_reports_dropped_blocks():
    pages = [["Abstract We study retrieval quality in some detail here.",
              "0.09", "Gain", "Score", "Binary", "0 100 200",
              "1 Introduction", "Retrieval matters because answers depend on evidence found."]]
    dropped = []
    text = clean_document(pages, dropped=dropped)
    assert "Gain" not in text and len(dropped) == 5
    assert "1 Introduction" in text and "Retrieval matters" in text


def test_label_soup_without_function_words_is_noise():
    soup = ("0 100 200 Training Step Single Obj. Two Obj. Single Obj. Two Obj. "
            "0 100 200 Training Step (a) SD3.5: In-Domain (b) FLUX: In-Domain (c) SD3.5: GenEval")
    assert is_noise_block(soup)


def test_long_headings_and_prose_without_stopwords_ending_are_kept():
    heading = "4.2 Verifier-Guided Reinforcement Learning for Rule-Governed Generative World Modeling"
    assert not is_noise_block(heading)
    caption = "Figure 1: Training curves of graded and binary verifiers on two image generators."
    assert not is_noise_block(caption)


def test_real_chart_fragments_are_dropped():
    blocks = [
        "0 100 200 Training Step", "0 100 200 Training Step",
        "Single Obj. Two Obj.", "Single Obj. Two Obj.", "0 100 200 Training Step",
        "A real sentence long enough to count as prose here.",
    ]
    dropped = []
    kept = drop_fragment_runs(blocks, dropped=dropped)
    assert kept == ["A real sentence long enough to count as prose here."]
    assert len(dropped) == 5


def test_panel_labels_do_not_count_as_function_words():
    labels = "(a) SD3.5: In-Domain (b) FLUX: In-Domain (c) SD3.5: GenEval (d) FLUX: GenEval"
    assert is_noise_block(labels)


def test_run_of_short_real_sentences_is_kept():
    blocks = ["We thank Alice.", "It works well.", "They agree with us.", "This is fine."]
    assert drop_fragment_runs(blocks) == blocks


def test_table_of_contents_blocks_are_dropped():
    toc = "156 6.7 Matador versus Dependency Gisting . . . . . . . . . . . . . . 162 6.8 Handling of Translation . . . . . . 164"
    assert is_toc_block(toc)
    assert is_toc_block("Introduction ........................ 3")
    pages = [["Abstract We study retrieval quality in some detail here.", toc,
              "1 Introduction", "Retrieval matters because answers depend on evidence found."]]
    dropped = []
    text = clean_document(pages, dropped=dropped)
    assert "Matador" not in text and toc in dropped


def test_normal_text_is_not_toc():
    assert not is_toc_block("Wait . . . what happened? We use e.g. U.S. data and A. B. Smith's method.")
    assert not is_toc_block("The result was stable (see Section 3.2 for details).")


def test_control_characters_and_lone_surrogates_are_stripped():
    assert clean_block("sym\x00bol\x0c text") == "symbol text"
    assert strip_control_chars("a\x00b\x07c") == "abc"
    assert strip_control_chars("a\ud835b") == "ab"  # a lone surrogate cannot be stored as UTF-8
    assert strip_control_chars("tab\tand\nnewline caf\u00e9") == "tab\tand\nnewline caf\u00e9"