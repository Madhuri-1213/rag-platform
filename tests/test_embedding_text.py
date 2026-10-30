from src.embedding.text import make_embed_key, make_embed_text


def test_title_and_section_are_prefixed():
    assert make_embed_text("A Paper", "Method", "We do things.") == "A Paper | Method\nWe do things."


def test_uninformative_sections_are_left_out():
    assert make_embed_text("A Paper", "Body", "Text.") == "A Paper\nText."
    assert make_embed_text("A Paper", "Preamble", "Text.") == "A Paper\nText."
    assert make_embed_text("A Paper", None, "Text.") == "A Paper\nText."


def test_embed_key_is_stable_and_sensitive():
    k = make_embed_key("model-a", "some text")
    assert k == make_embed_key("model-a", "some text")
    assert k != make_embed_key("model-b", "some text")
    assert k != make_embed_key("model-a", "some other text")
    assert len(k) == 64