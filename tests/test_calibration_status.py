'''
Tests for :mod:`cftscal.paradigms.calibration_status` -- the context item
reporting which calibration an object is using.
'''
import pytest

from cftscal.paradigms import calibration_status as cs
from cftscal.paradigms.calibration_status import (
    CalibrationParameter, NOT_CONFIGURED, NOT_LOADED, describe_calibration,
    report_calibration
)

from .fakes import FakeCalibration, FakeContext


class UndatedCalibration:
    '''
    A calibration that cannot report when it was measured -- the base
    class leaves `datetime` unimplemented, and calibrations predating the
    metadata sidecar raise when it is read.
    '''

    def __init__(self, name):
        self.name = name

    @property
    def datetime(self):
        raise FileNotFoundError('metadata.json')


class TestDescribeCalibration:

    def test_name_and_date(self):
        assert describe_calibration(FakeCalibration('mic_1')) == \
            'mic_1 (2025-06-12)'

    def test_missing_calibration(self):
        assert describe_calibration(None) == NOT_LOADED

    def test_undated_calibration_falls_back_to_name(self):
        # Not being able to date a calibration is not worth failing an
        # experiment over.
        assert describe_calibration(UndatedCalibration('mic_1')) == 'mic_1'


class TestCalibrationParameter:

    @pytest.fixture
    def item(self):
        return CalibrationParameter(name='mic_calibration',
                                    label='Microphone calibration')

    def test_read_only(self, item):
        assert item.editable is False
        assert item.scope == 'experiment'

    def test_starts_unconfigured(self, item):
        assert item.selected == NOT_CONFIGURED

    def test_displays_text_without_quotes(self, item):
        # The drop-down shows the choice keys, so this is what the user
        # sees. A plain string Parameter would instead be drawn as a
        # field showing the quoted expression.
        item.set_value('cal_a (2025-06-12)')
        assert list(item.choices) == ['cal_a (2025-06-12)']
        assert item.selected == 'cal_a (2025-06-12)'

    def test_expression_is_quoted(self, item):
        # The value of a context item is a Python expression, so an
        # unquoted string would be evaluated as a variable name.
        item.set_value('cal_a (2025-06-12)')
        assert item.expression == '"cal_a (2025-06-12)"'

    def test_default_expression_is_quoted(self, item):
        assert item.expression == f'"{NOT_CONFIGURED}"'

    def test_replaces_rather_than_accumulates_choices(self, item):
        item.set_value('cal_a (2025-06-12)')
        item.set_value('cal_b (2025-07-01)')
        assert list(item.choices) == ['cal_b (2025-07-01)']

    def test_choices_are_per_instance(self, item):
        # A default shared across instances would leak one object's
        # calibration into another's drop-down.
        other = CalibrationParameter(name='other_calibration')
        item.set_value('cal_a (2025-06-12)')
        assert list(other.choices) == [NOT_CONFIGURED]

    def test_dtype_is_not_fixed_width(self, item):
        # Taken from the choices by default, which would size it to
        # whatever is in there when the item is created and truncate
        # longer calibration names when the context is saved.
        assert item.dtype == 'U'


class TestReportCalibration:

    def test_loaded(self):
        context = FakeContext()
        report_calibration(context, 'mic_calibration',
                           FakeCalibration('cal_a'))
        assert context.items['mic_calibration'].value == 'cal_a (2025-06-12)'

    def test_not_loaded(self):
        # Reported explicitly rather than left looking unconfigured: the
        # hardware was selected, it just has no calibration.
        context = FakeContext()
        report_calibration(context, 'mic_calibration', None)
        assert context.items['mic_calibration'].value == NOT_LOADED


class FakeApplication:
    '''
    Stands in for the running enaml application.
    '''

    def __init__(self, main_thread):
        self.main_thread = main_thread

    def is_main_thread(self):
        return self.main_thread


class TestGuiCall:
    '''
    The handlers that report calibrations run on psi's control-plane
    thread, but updating the item reaches into the drop-down it is bound
    to, and refreshing a drop-down's items starts a Qt timer -- which Qt
    refuses to do off the GUI thread, and which psi escalates from a
    warning into an aborted experiment.
    '''

    def _patch_application(self, monkeypatch, app):
        monkeypatch.setattr(cs.Application, 'instance', staticmethod(lambda: app))
        calls = []
        monkeypatch.setattr(cs, 'deferred_call',
                            lambda fn, *args: calls.append((fn, args)))
        return calls

    def test_deferred_when_off_the_gui_thread(self, monkeypatch):
        calls = self._patch_application(monkeypatch,
                                        FakeApplication(main_thread=False))
        context = FakeContext()

        report_calibration(context, 'mic_calibration',
                           FakeCalibration('cal_a'))

        # Handed off rather than applied here.
        assert context.items['mic_calibration'].value is None
        fn, args = calls[0]
        fn(*args)
        assert context.items['mic_calibration'].value == 'cal_a (2025-06-12)'

    def test_direct_on_the_gui_thread(self, monkeypatch):
        calls = self._patch_application(monkeypatch,
                                        FakeApplication(main_thread=True))
        context = FakeContext()

        report_calibration(context, 'mic_calibration',
                           FakeCalibration('cal_a'))

        assert calls == []
        assert context.items['mic_calibration'].value == 'cal_a (2025-06-12)'

    def test_direct_without_an_application(self, monkeypatch):
        calls = self._patch_application(monkeypatch, None)
        context = FakeContext()

        report_calibration(context, 'mic_calibration', None)

        assert calls == []
        assert context.items['mic_calibration'].value == NOT_LOADED
