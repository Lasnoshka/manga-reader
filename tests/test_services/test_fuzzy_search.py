from app.services.fuzzy_search import fuzzy_rank, normalize, similarity


def test_normalize_strips_diacritics_and_lowercases():
    assert normalize("Bérsérk") == "berserk"
    assert normalize("  HELLO  ") == "hello"
    assert normalize(None) == ""


def test_similarity_exact_match_is_one():
    assert similarity("berserk", "berserk") == 1.0


def test_similarity_substring_scores_high():
    assert similarity("berserk", "berserk: black swordsman") > 0.9


def test_similarity_typo_passes_threshold():
    # 1 char swap out of 7 — should land >= 0.55
    assert similarity("berzerk", "berserk") >= 0.55


def test_fuzzy_rank_filters_below_threshold():
    candidates = [
        ("berserk", ["Berserk"]),
        ("naruto", ["Naruto"]),
        ("vinland", ["Vinland Saga"]),
    ]
    ranked = fuzzy_rank("berzerk", candidates)
    assert ranked
    assert ranked[0].item == "berserk"
    # naruto should not match
    assert all(r.item != "naruto" for r in ranked)


def test_fuzzy_rank_respects_limit():
    candidates = [(f"item{i}", [f"berserk variation {i}"]) for i in range(5)]
    ranked = fuzzy_rank("berserk", candidates, limit=2)
    assert len(ranked) == 2


def test_fuzzy_rank_with_empty_query_returns_empty():
    candidates = [("a", ["something"])]
    assert fuzzy_rank("", candidates) == []
