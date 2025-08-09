import re

from app.chunking import (
    is_heading_like,
    smart_split,
    split_by_sentences,
    split_into_chunks,
    take_last_sentences,
)
from app.models import count_tokens_rough


def test_split_into_chunks_overlap_and_token_limit():
    sentence = "Dies ist ein ziemlich langer Satz mit vielen Worten und endet hier."
    text = "HEAD1.\n" + sentence + "\nHEAD2.\n" + sentence
    chunks = split_into_chunks(text, target_tokens=20, overlap_tokens=17)

    assert len(chunks) == 3
    assert chunks[1].splitlines()[0].strip() == sentence
    assert all(count_tokens_rough(c) <= 20 for c in chunks)


def test_is_heading_like_detection():
    assert is_heading_like("1 Einleitung")
    assert not is_heading_like("This is just a sentence.")


def test_smart_split_respects_token_limit():
    para1 = "Sentence one."
    para2 = "Sentence two."
    text = f"{para1}\n\n{para2}"
    target = count_tokens_rough(para1)
    parts = smart_split(text, target_tokens=target, max_chars=1000)
    assert parts == [para1, para2]


def test_split_by_sentences_respects_token_limit():
    text = "First sentence. Second sentence. Third sentence."
    sents = re.split(r"(?<=[\.\?!])\s+", text)
    target = count_tokens_rough(sents[0])
    parts = split_by_sentences(text, target_tokens=target, max_chars=1000)
    assert parts == sents


def test_take_last_sentences_up_to_token_limit():
    text = "First sentence. Second sentence. Third sentence."
    sents = re.split(r"(?<=[\.\?!])\s+", text.strip())
    approx = count_tokens_rough(sents[-1]) + count_tokens_rough(sents[-2])
    result = take_last_sentences(text, approx_tokens=approx)
    assert result == " ".join(sents[-2:])
