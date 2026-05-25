"""Tests for lenient discussion plagiarism detection."""

from chcp.plagiarism.checker import (
    DiscussionPost,
    compare_posts,
    find_plagiarism_pairs,
    normalize_text,
    strip_prompt_from_text,
    word_count,
)


def _post(author_id: str, name: str, content: str) -> DiscussionPost:
    return DiscussionPost(author_id=author_id, full_name=name, content=content)


def test_normalize_text_strips_urls_and_punctuation():
    text = "Hello! See https://example.com/page for info."
    assert "hello" in normalize_text(text)
    assert "example.com" not in normalize_text(text)


def test_similar_topic_posts_not_flagged():
    """Same prompt restatement with different arguments should not match."""
    prompt = (
        "Explain how Newton's first law applies to a passenger in a car "
        "that brakes suddenly. Use at least two sentences and cite one source."
    )
    post_a = (
        "Newton's first law says an object in motion stays in motion unless acted on. "
        "When the car brakes, the seat belt applies force so the passenger stops with the car. "
        "I read about this in our textbook chapter on inertia and force pairs."
    )
    post_b = (
        "Newton's first law describes inertia: bodies resist changes in motion. "
        "During hard braking the passenger would keep moving forward without a seat belt. "
        "My example is a grocery cart rolling until someone grabs the handle."
    )
    match = compare_posts(
        _post("1", "Alice, A", post_a),
        _post("2", "Bob, B", post_b),
        prompt=prompt,
    )
    assert match is None


def test_near_duplicate_posts_flagged():
    body = (
        "The coefficient of friction between rubber and dry asphalt is typically "
        "around 0.7 for passenger tires under normal load. When rain reduces contact "
        "patch grip, stopping distance increases because the maximum static friction "
        "force available for deceleration drops. Fleet safety data from the NHTSA "
        "shows wet-road collisions rise sharply above 45 mph in light trucks. "
        "Drivers should increase following distance proportionally to the square of speed "
        "because kinetic energy scales with velocity squared. In our lab we measured "
        "μ ≈ 0.65 on a cleaned concrete pad using a force gauge and weighted sled. "
    )
    copy = body + " Minor wording tweak at the end."
    matches = find_plagiarism_pairs(
        [_post("1", "One, Student", body), _post("2", "Two, Student", copy)],
        similarity_threshold=0.92,
        min_words=80,
    )
    assert len(matches) == 1
    assert matches[0].similarity_ratio >= 0.92


def test_short_posts_skipped():
    short = "This is only a brief answer without enough depth."
    long_post = "word " * 100
    match = compare_posts(_post("1", "A", short), _post("2", "B", long_post))
    assert match is None


def test_same_author_not_compared():
    text = "word " * 100
    matches = find_plagiarism_pairs(
        [_post("1", "A", text), _post("1", "A", text)],
    )
    assert matches == []


def test_strip_prompt_removes_long_prompt_sentence():
    prompt = "Explain the photoelectric effect and cite one peer-reviewed source in APA format."
    post = prompt + " " + ("Additional unique analysis " * 20)
    stripped = strip_prompt_from_text(post, prompt)
    assert normalize_text(prompt) not in stripped or word_count(stripped) >= 50
