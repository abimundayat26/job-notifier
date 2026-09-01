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


def test_is_us_location_state_abbreviation():
    assert normalize.is_us_location("New York, NY")
    assert normalize.is_us_location("Austin, TX")


def test_is_us_location_dc_variants():
    assert normalize.is_us_location("Washington, DC")
    assert normalize.is_us_location("Washington, D.C")
    assert normalize.is_us_location("Washington, D.C.")


def test_is_us_location_bare_state_name():
    assert normalize.is_us_location("Georgia")
    assert normalize.is_us_location("California")


def test_is_us_location_bare_united_states():
    assert normalize.is_us_location("United States")


def test_is_us_location_remote_in_usa_variants():
    assert normalize.is_us_location("Remote in USA")
    assert normalize.is_us_location("Remote in US")
    assert normalize.is_us_location("Remote - US")
    assert normalize.is_us_location("Remote (US)")


def test_is_us_location_bare_remote_is_ambiguous_and_not_excluded():
    # No country signal at all -- SPEC.md §9's ambiguity philosophy applied
    # to filtering: don't guess it's non-US and silently drop it.
    assert normalize.is_us_location("Remote")


def test_is_us_location_city_alias_without_state():
    assert normalize.is_us_location("NYC")
    assert normalize.is_us_location("SF")
    assert normalize.is_us_location("South SF")


def test_is_us_location_rejects_other_countries():
    assert not normalize.is_us_location("London, UK")
    assert not normalize.is_us_location("Toronto, ON, Canada")
    assert not normalize.is_us_location("France")
    assert not normalize.is_us_location("Bangalore, India")


def test_is_us_location_rejects_non_us_remote():
    assert not normalize.is_us_location("Remote in Canada")
    assert not normalize.is_us_location("Remote in UK")


def test_is_us_location_merged_multi_location_passes_if_any_office_is_us():
    assert normalize.is_us_location("London, UK; New York, NY")
    assert normalize.is_us_location("Birmingham, UK; NYC; SF")


def test_is_us_location_merged_multi_location_all_non_us_excluded():
    assert not normalize.is_us_location("Birmingham, UK; London, UK")
    assert not normalize.is_us_location("Calgary, AB, Canada; Toronto, ON, Canada")
