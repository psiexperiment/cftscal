'''
Tests for :func:`cftscal.util.slugify`.
'''
import pytest

from cftscal.util import slugify


@pytest.mark.parametrize('text, expected', [
    ('MMM0', 'mmm0'),
    ('Bench speaker #3 (Lab B)', 'bench-speaker-3-lab-b'),
    # Characters Windows forbids in folder names, and '/', which would
    # otherwise create extra subfolders.
    (r'C:/a<b>c|d?e*f"g\h', 'c-a-b-c-d-e-f-g-h'),
    ('Café', 'cafe'),
    ('  --leading and trailing--  ', 'leading-and-trailing'),
    ('a   b', 'a-b'),
    ('???', ''),
    ('', ''),
])
def test_slugify(text, expected):
    assert slugify(text) == expected
