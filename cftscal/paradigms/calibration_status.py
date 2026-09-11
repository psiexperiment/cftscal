'''
Reports which calibration an object is actually using.

Whether a gain or a channel selection was picked up from the environment
is obvious from the GUI -- the value is sitting right there in the
widget. A calibration is not: it is loaded onto the psi channel
(``channel.calibration``), which has no widget at all, and a channel
whose calibration was never set is not empty but silently defaults to
``FlatCalibration.unity()`` (see ``Channel.calibration`` in
psiexperiment's ``psi/controller/channel.py``). An experiment running
against a unity calibration looks exactly like one running against a
real calibration until the data is analyzed.

:class:`CalibrationParameter` makes that state visible. It is a
read-only context item that sits with the object's other hardware
settings and names the calibration that was loaded (or says it was not).
Being a context item, it is also saved with the experiment data, so the
recording itself records which calibration produced it.
'''
import logging
log = logging.getLogger(__name__)

from atom.api import set_default

from enaml.application import Application, deferred_call

from psi.context.api import EnumParameter


#: Shown before an object has been configured at all (e.g., the
#: environment variable naming the hardware was not set).
NOT_CONFIGURED = 'not configured'

#: Shown when the hardware was selected but no calibration was loaded for
#: it. The channel is therefore using the unity calibration psi falls
#: back to.
NOT_LOADED = 'NOT LOADED'


def describe_calibration(calibration):
    '''
    Return a short description of a calibration for display in the GUI.

    Parameters
    ----------
    calibration : {None, instance of `cftscal.objects.Calibration`}
        The calibration that was loaded, or None if none was.

    Returns
    -------
    description : str
        The calibration name and, when it can be determined, the date it
        was measured on. `NOT_LOADED` if `calibration` is None.
    '''
    if calibration is None:
        return NOT_LOADED
    try:
        return f'{calibration.name} ({calibration.datetime:%Y-%m-%d})'
    except Exception as exc:
        # Not every calibration can report a date. The base class leaves
        # `datetime` unimplemented, calibrations that predate the
        # metadata sidecar raise FileNotFoundError, and a malformed
        # sidecar raises while parsing. None of that is worth failing an
        # experiment over -- the name alone still identifies it.
        log.info('Could not determine date for calibration %s (%r)',
                 calibration.name, exc)
        return calibration.name


class CalibrationParameter(EnumParameter):
    '''
    Context item naming the calibration an object is using.

    Read-only: the value is set by the object's initialization handler,
    not by the user.

    Subclasses `EnumParameter` (with a single choice) rather than
    `Parameter` purely for how it is drawn. The value of a context item
    is a Python *expression*, so a plain string parameter holds
    ``'"mic_1 (2025-06-12)"'`` and psi's default widget -- a text field
    bound straight to the expression -- shows it with the quotes. An
    `EnumParameter` is drawn as a drop-down showing the *key* of the
    selected choice, which is the text as written here, while the quoted
    expression stays out of sight where the context evaluates it.
    '''
    editable = set_default(False)
    scope = set_default('experiment')
    default = set_default(NOT_CONFIGURED)

    #: Taken from the choices by default, which would make it a
    #: fixed-width string sized to whatever is in there when the item is
    #: created -- long calibration names would then be truncated when the
    #: context is saved.
    dtype = set_default('U')

    def _default_choices(self):
        # Quoting here rather than via `to_expression`, which looks at
        # `choices` and would therefore recurse into this default.
        return {self.default: f'"{self.default}"'}

    def set_value(self, value):
        # The drop-down displays the key, so the text to display is the
        # key and the quoted expression is the value. Assigning
        # `expression` directly (what the base class does) would fail,
        # since an EnumParameter only accepts expressions already among
        # its choices.
        self.choices = {value: f'"{value}"'}
        self.selected = value


def gui_call(fn, *args):
    '''
    Run `fn` on the GUI thread, waiting for no result.

    The handlers that report calibrations run at ``plugins_started``,
    which psi dispatches on its control-plane thread (see
    ``ControllerPlugin.invoke_actions`` in psiexperiment), not on the
    thread that owns the Qt event loop. Updating a
    :class:`CalibrationParameter` from there reaches into the drop-down
    it is bound to, and refreshing a drop-down's items starts a Qt timer
    -- which Qt refuses to do from a thread with no event loop
    ("QObject::startTimer: current thread's event dispatcher has already
    been destroyed"). psi turns Qt warnings into hard errors, so this
    aborts the experiment rather than merely printing a complaint.

    If there is no application running (a test, or a headless script) or
    we are already on the GUI thread, `fn` is called directly.
    '''
    app = Application.instance()
    if app is None or app.is_main_thread():
        fn(*args)
    else:
        deferred_call(fn, *args)


def report_calibration(context, item_name, calibration):
    '''
    Show which calibration was loaded for one piece of hardware.

    Parameters
    ----------
    context : psi context plugin
        Plugin holding the context items.
    item_name : str
        Name of the `CalibrationParameter` to update.
    calibration : {None, instance of `cftscal.objects.Calibration`}
        The calibration that was loaded, or None if none was (in which
        case the item reports that the hardware is uncalibrated, rather
        than leaving it looking unconfigured).
    '''
    item = context.get_item(item_name)
    gui_call(item.set_value, describe_calibration(calibration))
