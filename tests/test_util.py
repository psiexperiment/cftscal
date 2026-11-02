'''
Tests for :func:`cftscal.util.slugify`.
'''
import pytest

from cftscal.util import natural_sort_key, slugify


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


@pytest.mark.parametrize('labels, expected', [
    # The order sound cards number their channels in, not "1, 10, 11, 2".
    (['Output 10', 'Output 2', 'Output 1', 'Output 19', 'Output 0'],
     ['Output 0', 'Output 1', 'Output 2', 'Output 10', 'Output 19']),
    (['Speaker 2 (right)', 'Speaker 1 (left)'],
     ['Speaker 1 (left)', 'Speaker 2 (right)']),
    # Text before the number sorts first, ignoring case.
    (['input 2', 'Input 1', 'Analog 10', 'analog 9'],
     ['analog 9', 'Analog 10', 'Input 1', 'input 2']),
    # Labels without numbers, or starting with one, still sort.
    (['b', '10 a', 'a', '9 a'], ['9 a', '10 a', 'a', 'b']),
])
def test_natural_sort_key(labels, expected):
    assert sorted(labels, key=natural_sort_key) == expected
