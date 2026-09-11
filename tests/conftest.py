import os

import pytest

from .fakes import FakeEvent


@pytest.fixture
def event(monkeypatch):
    '''
    A workbench event for a paradigm's initialization handler, with an
    empty environment so a test only sees the variables it sets itself.
    '''
    monkeypatch.setattr(os, 'environ', {})
    return FakeEvent()
