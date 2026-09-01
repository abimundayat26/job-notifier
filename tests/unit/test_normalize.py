from jobnotifier import normalize


def test_normalize_company_lowercases_and_trims():
    assert normalize.normalize_company("  Citadel  ") == "citadel"


def test_normalize_title_collapses_whitespace():
    assert normalize.normalize_title("Software   Engineer\tIntern") == "software engineer intern"


def test_normalize_location_alias_nyc():
    assert normalize.normalize_location("NYC") == normalize.normalize_location("New York, NY")


def test_normalize_location_no_alias_passthrough():
    assert normalize.normalize_location("Austin, TX") == "austin, tx"


def test_location_matches_filter_via_alias():
    assert normalize.location_matches_filter("NYC", ["New York, NY", "Remote"])


def test_location_matches_filter_no_match():
    assert not normalize.location_matches_filter("Austin, TX", ["New York, NY", "Remote"])


def test_merge_locations_dedupes_and_sorts():
    assert normalize.merge_locations(["NYC", "Austin, TX", "NYC"]) == "Austin, TX; NYC"


def test_merge_locations_order_independent():
    # A source reordering its own list between fetches must not change the
    # merged result, or canonical_key() would treat the same job as new.
    assert normalize.merge_locations(["B", "A"]) == normalize.merge_locations(["A", "B"])


def test_merge_locations_empty_list_is_empty_string():
    assert normalize.merge_locations([""]) == ""
    assert normalize.merge_locations([]) == ""
