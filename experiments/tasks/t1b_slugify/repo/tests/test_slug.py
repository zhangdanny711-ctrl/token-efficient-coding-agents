from slugkit import slugify, unique_slug


def test_basic():
    assert slugify("Hello, World!") == "hello-world"


def test_accents():
    assert slugify("Crème Brûlée") == "creme-brulee"


def test_collapse_separators():
    assert slugify("a  --  b") == "a-b"


def test_truncation_keeps_words_whole():
    # max_length 8: "abc-def-ghi" should truncate to "abc-def", not "abc-def-"
    assert slugify("abc def ghi", max_length=8) == "abc-def"


def test_truncation_exact_fit():
    assert slugify("abc def", max_length=7) == "abc-def"


def test_unique_slug():
    assert unique_slug("Hello", {"hello"}) == "hello-2"
    assert unique_slug("Hello", {"hello", "hello-2"}) == "hello-3"
