from textstats import (
    average_word_length,
    char_frequencies,
    longest_word,
    word_count,
)


def test_word_count():
    assert word_count("the quick brown fox") == 4
    assert word_count("") == 0


def test_char_frequencies():
    assert char_frequencies("aab") == {"a": 2, "b": 1}


def test_average_word_length_simple():
    # "ab cd" -> two words of length 2 -> mean 2.0
    assert average_word_length("ab cd") == 2.0


def test_average_word_length_empty():
    assert average_word_length("") == 0.0


def test_longest_word():
    assert longest_word("a bb ccc") == "ccc"
    assert longest_word("") == ""
