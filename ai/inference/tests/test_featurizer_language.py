import numpy as np
import pytest

from ai.inference.language import detect_language
from ai.inference.local.featurizer import CharNgramVectorizer, char_wb_ngrams, count_ngrams, normalize_text


def test_normalisation():
    assert normalize_text("  Pothole!! at Shivaji-Nagar। ") == "pothole at shivaji nagar"
    assert normalize_text("PoThOlE") == "pothole"
    assert normalize_text("गड्ढा‍ है") == normalize_text("गड्ढा है")  # zero-width chars dropped
    assert "गड्ढा" in normalize_text("गड्ढा") or normalize_text("गड्ढा")  # Devanagari retained
    assert normalize_text("") == "" and normalize_text("!!!") == ""


def test_char_wb_ngrams_are_word_bounded():
    g = list(char_wb_ngrams("ab", (2, 3)))
    assert g == [" a", "ab", "b ", " ab", "ab "]
    assert list(char_wb_ngrams("", (2, 4))) == []
    assert sum(count_ngrams("aa aa").values()) == 2 * len(list(char_wb_ngrams("aa", (2, 4))))


def make_vec():
    vocab = {g: i for i, g in enumerate(sorted(count_ngrams("pothole road").keys()))}
    return CharNgramVectorizer(vocab, np.ones(len(vocab), dtype=np.float32), (2, 4))


def test_vectoriser_is_l2_normalised_sorted_and_deterministic():
    v = make_vec()
    idx, val = v.transform_one("big pothole")
    assert np.all(np.diff(idx) > 0) and abs(float(np.linalg.norm(val)) - 1.0) < 1e-5
    idx2, val2 = v.transform_one("big pothole")
    assert np.array_equal(idx, idx2) and np.array_equal(val, val2)


def test_vectoriser_unknown_or_empty_text_gives_empty_vector():
    v = make_vec()
    for t in ("", "zzzz", "!!!"):
        idx, val = v.transform_one(t)
        assert idx.size == 0 and val.size == 0


def test_vectoriser_validates_shapes():
    with pytest.raises(ValueError):
        CharNgramVectorizer({"a": 0}, np.ones(2), (2, 4))


@pytest.mark.parametrize("text,expected", [
    ("There is a big pothole near the school", "en"),
    ("सड़क पर बड़ा गड्ढा है", "hi"),
    ("रस्त्यावर मोठा खड्डा पडला आहे", "mr"),
    ("sadak par bada gadda hai bahut din se", "hi-Latn"),
    ("", "en"),
])
def test_language_detection(text, expected):
    assert detect_language(text) == expected


def test_language_hint_only_used_when_text_is_empty_or_ambiguous():
    assert detect_language("", "mr") == "mr"
    assert detect_language("There is a pothole", "mr") == "en"
