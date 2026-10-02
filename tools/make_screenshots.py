'''
Make the screenshots in the user guide (docs/images) from real data.

Usage::

    python tools/make_screenshots.py C:/path/to/cftscal-data

where the folder is a calibration root (what CFTSCAL_ROOT points at)
holding the ``microphone/`` and ``input-recording/`` calibrations listed
in COPY. It is
copied to a temporary folder first and only the copy is used, so nothing
is ever written back to it. A temporary configuration file is used too,
so the screenshots don't depend on (or change) this computer's settings.

Rerun it whenever a workspace's layout changes. The device names, folders
and notes in the data appear in the images, which are published on the
website. The Home and Help shots show the bundled user guide, so run
tools/build_guide.py first (otherwise they show the website).
'''
import argparse
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

#: Window size the screenshots are taken at, in pixels.
SIZE = (1200, 760)

#: What is copied from the data for the screenshots: each workspace's
#: folder, limited to the object folders listed (None copies them all).
#: Only what the screenshots show is copied, so other labs' folders don't
#: end up on the website.
COPY = {
    'microphone': None,
    'input-recording': ['BK-4123'],
}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('data', type=Path,
                        help='calibration root to take the screenshots from')
    parser.add_argument('--out', type=Path,
                        default=Path(__file__).parents[1] / 'docs' / 'images',
                        help='where to save the images (default: docs/images)')
    return parser.parse_args()


def isolate(data):
    '''
    Copy the data to a temporary folder and point cftscal at it, with an
    empty configuration of its own. Must run before cftscal is imported:
    its calibration loaders read CFTSCAL_ROOT when they are created.
    '''
    tmp = Path(tempfile.mkdtemp(prefix='cftscal-screenshots-'))
    root = tmp / 'cftscal'
    for name, objects in COPY.items():
        if not (data / name).is_dir():
            continue
        if objects is None:
            shutil.copytree(data / name, root / name)
        else:
            for obj in objects:
                shutil.copytree(data / name / obj, root / name / obj)
    os.environ['CFTSCAL_ROOT'] = str(root)
    os.environ['PSI_CONFIG_FILE'] = str(tmp / 'config.toml')
    os.environ['PSI_CONFIG'] = str(tmp / 'legacy')
    return tmp


def settle(app, rounds=20):
    '''Let Qt finish layout and painting before a grab.'''
    for _ in range(rounds):
        app.processEvents()


def show(view, title):
    '''Show a workspace view in a window of the standard size.'''
    import enaml
    with enaml.imports():
        from enaml.widgets.api import Container, Window
    window = Window(title=title, initial_size=SIZE)
    container = Container(window, padding=0)
    view.set_parent(container)
    window.show()
    return window


def tick(tree, name, *dates):
    '''
    Tick calibrations in a tree to plot them: those of the object ``name``
    whose folder starts with one of ``dates`` (e.g. '20260205-1039'), or
    its newest one if no dates are given.
    '''
    group = next(g for g in tree.collection.groups if g.item.name == name)
    nodes = group.subitems
    if dates:
        nodes = [n for n in nodes if n.item.filename.name.startswith(dates)]
    else:
        nodes = nodes[-1:]
    for node in nodes:
        node.selected = True
    return nodes


def only(view, type_name):
    '''The one widget of a type in a view (enaml's find() looks up the
    ``name`` attribute, not the ``mic_tree:``-style identifiers).'''
    found = [w for w in view.traverse() if type(w).__name__ == type_name]
    assert len(found) == 1, (type_name, found)
    return found[0]


def expand(tree, scroll_to=()):
    '''Expand every folder, then scroll so ``scroll_to`` (nodes) show.'''
    widget = only(tree, 'FastTreeView').view
    widget.expandAll()
    for node in scroll_to:
        widget.scrollToItem(widget._item_map[id(node)])


def wait(app, seconds):
    '''Keep Qt running for a while, e.g. while a guide page loads.'''
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.05)


def with_help_tab(view, page):
    '''Add the Help tab every workspace gets in the app (see help_tab).'''
    import enaml
    with enaml.imports():
        from cftscal.plugins.help_tab import add_help_tab
    add_help_tab(view, page)
    return view


def open_help_tab(window, app):
    '''Slide the Help tab open, as clicking it does, and let it load.'''
    from qtpy.QtWidgets import QAbstractButton
    tab, = [b for b in window.proxy.widget.findChildren(QAbstractButton)
            if b.text() == 'Help' and b.isVisible()]
    tab.click()
    wait(app, 5)


def save(window, app, path):
    settle(app)
    path.parent.mkdir(parents=True, exist_ok=True)
    window.proxy.widget.grab().save(str(path))
    print('saved', path)


def measurement_microphone(app, out):
    import enaml
    with enaml.imports():
        from cftscal.plugins.microphone.view import MicrophoneView
    from cftscal.plugins.microphone.settings import MicrophoneCalibrationSettings

    settings = MicrophoneCalibrationSettings(
        {'Left Input': 'left_input', 'Right Input': 'right_input'})
    settings.pistonphone.name = 'B&K-4231'
    settings.pistonphone.frequency = 1000
    settings.pistonphone.level = 114
    sensor = settings.selected_input.sensor
    sensor.available_devices = ['HATS-Left', 'HATS-Right']
    sensor.name = 'HATS-Left'

    view = with_help_tab(MicrophoneView(settings=settings),
                         'plugins/measurement-microphone')
    window = show(view, 'Measurement Microphone Calibration')
    tree = only(view, 'CalibratedObjects')
    tick(tree, 'HATS-Left')
    tick(tree, 'HATS-Right')
    expand(tree)
    save(window, app, out / 'measurement-microphone' / 'workspace.png')
    # The same workspace with its Help tab open.
    open_help_tab(window, app)
    save(window, app, out / 'help-tab.png')
    window.close()


def input_recording(app, out):
    import enaml
    with enaml.imports():
        from cftscal.plugins.input_recording.view import InputRecordingView
    from cftscal.plugins.input_recording.settings import InputRecordingSettings

    settings = InputRecordingSettings(
        {'Left Input': 'left_input', 'Right Input': 'right_input'})
    settings.n_active_inputs = 2
    for channel, mic in zip(settings.available_inputs, ('HATS-Left', 'HATS-Right')):
        channel.sensor.refresh_available()
        channel.sensor.name = mic
    settings.generator.name = 'BK-4123'

    view = with_help_tab(InputRecordingView(settings=settings),
                         'plugins/input-recording')
    window = show(view, 'Input Recording')
    tree = only(view, 'CalibratedObjects')
    # The newest recording through each ear's microphone (top of the list).
    nodes = tick(tree, 'BK-4123', '20260616-101544', '20260616-101247')
    expand(tree, nodes)
    manager = only(view, 'PGCanvas').manager
    settle(app)
    # Over the tone bursts, so the Analysis table measures the signal.
    manager.region_select.setRegion((18, 22))
    save(window, app, out / 'input-recording' / 'workspace.png')
    window.close()


def home(app, out):
    '''Home, with a tile for every calibration workspace.'''
    import importlib
    import enaml
    from enaml.workbench.api import Workbench
    with enaml.imports():
        from enaml.workbench.core.core_manifest import CoreManifest
        from enaml.workbench.ui.ui_manifest import UIManifest
        from cftscal.plugins.home_view import HomeView
        from cftscal.plugins.manifest import CalibrationManifest, TO_REGISTER
        workbench = Workbench()
        workbench.register(CoreManifest())
        workbench.register(UIManifest())
        workbench.register(CalibrationManifest())
        for rank, (module_name, class_name) in enumerate(TO_REGISTER):
            cls = getattr(importlib.import_module(module_name), class_name)
            workbench.register(cls(rank=rank))
    window = show(HomeView(workbench=workbench), 'Home')
    wait(app, 15)  # the User Guide panel loading (the first web view starts the engine)
    save(window, app, out / 'home.png')
    window.close()


def main():
    args = parse_args()
    if not args.data.is_dir():
        sys.exit(f'{args.data} is not a folder')
    tmp = isolate(args.data)
    try:
        from cftscal.plugins.guide_view import prepare_web_engine
        prepare_web_engine()  # before the Qt application, as in cfts-cal
        from enaml.qt.qt_application import QtApplication
        app = QtApplication()
        from qtpy.QtWidgets import QApplication
        qapp = QApplication.instance()
        home(qapp, args.out)
        measurement_microphone(qapp, args.out)
        input_recording(qapp, args.out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
