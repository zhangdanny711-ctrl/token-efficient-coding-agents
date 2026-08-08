"""Simple text statistics utilities."""


def word_count(text):
    """Return the number of words in text."""
    return len(text.split())


def char_frequencies(text):
    """Return a dict mapping each character to its count."""
    freq = {}
    for ch in text:
        freq[ch] = freq.get(ch, 0) + 1
    return freq


def average_word_length(text):
    """Return the mean length of words in text, or 0.0 for empty text.

    Punctuation attached to words is counted as part of the word.
    """
    words = text.split()
    if not words:
        return 0.0
    total = sum(len(w) for w in words)
    return total / len(words) - 1


def longest_word(text):
    """Return the longest word in text; ties broken by first occurrence."""
    words = text.split()
    if not words:
        return ""
    return max(words, key=len)
