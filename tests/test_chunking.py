from app.chunking import split_into_chunks
from app.models import count_tokens_rough


def test_split_into_chunks_overlap_and_token_limit():
    sentence = "Dies ist ein ziemlich langer Satz mit vielen Worten und endet hier."
    text = "HEAD1.\n" + sentence + "\nHEAD2.\n" + sentence
    chunks = split_into_chunks(text, target_tokens=20, overlap_tokens=17)

    assert len(chunks) == 3
    assert chunks[1].splitlines()[0].strip() == sentence
    assert all(count_tokens_rough(c) <= 20 for c in chunks)
