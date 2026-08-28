from jobnotifier.models import Posting, canonical_key


def _posting(**overrides):
    defaults = dict(
        company="Citadel",
        title="Quantitative Researcher",
        location="NYC",
        url="https://example.com/job/1",
    )
    defaults.update(overrides)
    return Posting(**defaults)


def test_canonical_key_stable_for_identical_normalized_fields():
    a = _posting()
    b = _posting()
    assert canonical_key(a) == canonical_key(b)


def test_canonical_key_collapses_location_alias():
    a = _posting(location="NYC")
    b = _posting(location="New York, NY")
    assert canonical_key(a) == canonical_key(b)


def test_canonical_key_differs_on_distinct_location():
    a = _posting(location="NYC")
    b = _posting(location="Houston, TX")
    assert canonical_key(a) != canonical_key(b)


def test_canonical_key_differs_on_distinct_title():
    a = _posting(title="Quantitative Researcher")
    b = _posting(title="Quantitative Developer")
    assert canonical_key(a) != canonical_key(b)
