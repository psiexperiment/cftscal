'''
Notes attached to a calibration from the tree's right-click "Edit note…"
item. The note lives in the calibration's own ``metadata.json``, so it
travels with the folder and needs no separate storage.
'''
import json
from pathlib import Path

import enaml
import pytest

from cftscal.objects import (
    CalibrationManager, CFTSInputRecording, CFTSInputRecordingLoader,
    CalibratedObject,
)
from cftscal.plugins.object_collection import ObjectCollection


METADATA = {
    'datetime': '2026-01-01T00:00:00',
    'generator': 'Bench speaker #3',
    'sensors': {'ai0': {'label': 'Ch 0', 'sensor': 'unity', 'gain': 0.0}},
}


def _write_recording(path, metadata=METADATA):
    path.mkdir(parents=True)
    (path / 'metadata.json').write_text(json.dumps(metadata))
    return path


def _read(path):
    return json.loads((path / 'metadata.json').read_text())


class TestSetNote:

    def test_no_note_by_default(self, tmp_path):
        rec = CFTSInputRecording('rec', _write_recording(tmp_path / 'r'))
        assert rec.note == ''

    def test_note_is_saved_and_other_fields_kept(self, tmp_path):
        path = _write_recording(tmp_path / 'r')
        rec = CFTSInputRecording('rec', path)
        rec.metadata  # cache it first, as the tree already will have
        rec.set_note('  Left ear probe slipped at ~3 s.\nRepeat.  ')
        assert _read(path) == {**METADATA, 'note': 'Left ear probe slipped at ~3 s.\nRepeat.'}
        # The cached copy is updated too, not just the file.
        assert rec.note == 'Left ear probe slipped at ~3 s.\nRepeat.'
        # ...and a fresh object sees it.
        assert CFTSInputRecording('rec', path).note == rec.note

    def test_empty_note_removes_field(self, tmp_path):
        path = _write_recording(tmp_path / 'r', {**METADATA, 'note': 'old'})
        rec = CFTSInputRecording('rec', path)
        rec.set_note('   ')
        assert 'note' not in _read(path)
        assert rec.note == ''

    def test_does_not_restore_stale_cached_fields(self, tmp_path):
        # Something else (e.g. a metadata migration) changed the file
        # after it was cached -- saving a note must not undo that.
        path = _write_recording(tmp_path / 'r')
        rec = CFTSInputRecording('rec', path)
        rec.metadata
        (path / 'metadata.json').write_text(
            json.dumps({**METADATA, 'generator': 'renamed'}))
        rec.set_note('hi')
        assert _read(path)['generator'] == 'renamed'


class _Loader(CFTSInputRecordingLoader):
    '''Bypass CFTSBaseLoader.__init__ so tests can point at tmp_path.'''

    def __init__(self, base_path):
        self.base_path = Path(base_path)


class TestTreeNotes:
    '''
    Every tree offers "Edit note…" on any calibration that has a
    metadata.json, and marks noted rows with a sticky-note icon plus a
    tooltip showing the note.
    '''

    @pytest.fixture
    def tree(self, qt_app, tmp_path):
        _write_recording(tmp_path / 'Lab' / '20260101-000000_rec')
        manager = CalibrationManager(CalibratedObject)
        manager.loaders.append(_Loader(tmp_path))
        with enaml.imports():
            from cftscal.plugins.fast_tree_view import FastTreeWidget
        mapping = {
            'name': {'groupby': True, 'id': True, 'to_str': lambda x: x.name},
            'generator': {'to_str': lambda x: x.generator},
        }
        collection = ObjectCollection(manager, [])
        return FastTreeWidget(None, mapping, collection)

    def _node(self, tree):
        return tree.collection.groups[0].subitems[0]

    def _leaf_item(self, tree):
        return tree.topLevelItem(0).child(0)

    def _menu_texts(self, tree, monkeypatch, node):
        from qtpy.QtCore import QPoint
        from qtpy.QtWidgets import QMenu
        seen = []

        def fake_exec(menu, *args):
            seen.extend(a.text() for a in menu.actions())
            return None

        monkeypatch.setattr(QMenu, 'exec_', fake_exec)
        tree._context_menu_for_leaf(node, QPoint())
        return seen

    def _fake_dialog(self, monkeypatch, result, prefilled=None):
        from qtpy.QtWidgets import QInputDialog

        def fake(parent, title, label, text):
            if prefilled is not None:
                prefilled.append(text)
            return result

        monkeypatch.setattr(QInputDialog, 'getMultiLineText', fake)

    def test_menu_item_without_opting_in(self, tree, monkeypatch):
        assert 'Edit note…' in self._menu_texts(tree, monkeypatch, self._node(tree))

    def test_no_menu_item_for_calibration_without_metadata(self, tree, monkeypatch):
        # e.g. unity: there's no metadata.json to store a note in.
        from types import SimpleNamespace
        from cftscal.objects import UnityInputCalibration
        node = SimpleNamespace(item=UnityInputCalibration(), problem=None)
        assert 'Edit note…' not in self._menu_texts(tree, monkeypatch, node)

    def _marks(self, item):
        '''Icons drawn after the row's name, as 'note'/'other'.'''
        from cftscal.plugins.fast_tree_view import MARKS_ROLE, note_icon
        key = note_icon().cacheKey()
        return ['note' if i.cacheKey() == key else 'other'
                for i in item.data(0, MARKS_ROLE) or []]

    def test_no_icon_or_tooltip_without_note(self, tree):
        item = self._leaf_item(tree)
        assert self._marks(item) == []
        assert item.icon(0).isNull()
        assert item.toolTip(0) == ''

    def test_note_icon_is_drawn(self, qt_app):
        with enaml.imports():
            from cftscal.plugins.fast_tree_view import note_icon
        icon = note_icon()
        assert not icon.isNull()
        assert {s.width() for s in icon.availableSizes()} == {16, 32}

    def test_edit_note_saves_and_marks_row(self, tree, monkeypatch):
        prefilled = []
        self._fake_dialog(monkeypatch, ('Probe slipped\nat 3 s', True), prefilled)
        node = self._node(tree)
        tree._edit_note(node)
        assert prefilled == ['']
        assert _read(node.item.filename)['note'] == 'Probe slipped\nat 3 s'

        item = self._leaf_item(tree)
        assert self._marks(item) == ['note']
        # Not in Qt's icon slot before the name (it's drawn after it),
        # and the name itself is left alone.
        assert item.icon(0).isNull()
        assert item.text(0) == '20260101-000000_rec'
        # Hovering anywhere on the row shows just the note.
        for col in range(tree.columnCount()):
            assert item.toolTip(col) == 'Probe slipped\nat 3 s'

        # Editing again pre-fills the dialog with the saved note.
        tree._edit_note(self._node(tree))
        assert prefilled[-1] == 'Probe slipped\nat 3 s'

    def test_clearing_note_removes_icon(self, tree, monkeypatch):
        self._node(tree).item.set_note('old')
        tree.populate_tree()
        assert self._marks(self._leaf_item(tree)) == ['note']
        self._fake_dialog(monkeypatch, ('', True))
        tree._edit_note(self._node(tree))
        item = self._leaf_item(tree)
        assert self._marks(item) == []
        assert item.toolTip(0) == ''

    def test_cancel_leaves_note_alone(self, tree, monkeypatch):
        node = self._node(tree)
        node.item.set_note('keep me')
        self._fake_dialog(monkeypatch, ('', False))
        tree._edit_note(node)
        assert _read(node.item.filename)['note'] == 'keep me'

    def test_problem_and_note_together(self, tree):
        self._node(tree).item.set_note('see log')
        tree.populate_tree()
        item = self._leaf_item(tree)
        self._node(tree).problem = 'Could not plot calibration: boom'
        # Both icons: warning first, then the note.
        assert self._marks(item) == ['other', 'note']
        assert item.toolTip(0) == 'Could not plot calibration: boom\n\nsee log'
        self._node(tree).problem = ''
        assert self._marks(item) == ['note']
        assert item.toolTip(0) == 'see log'

    def test_icon_is_painted_after_the_name(self, tree, qt_app):
        # Render the tree and look for the note's yellow: it must all be
        # to the right of the name, none of it before.
        from qtpy.QtGui import QColor
        from qtpy.QtWidgets import QApplication
        self._node(tree).item.set_note('see log')
        tree.populate_tree()
        tree.expandAll()
        tree.resize(600, 200)
        tree.show()
        QApplication.processEvents()
        item = self._leaf_item(tree)
        rect = tree.visualItemRect(item)
        image = tree.viewport().grab().toImage()
        yellow = QColor('#ffd94a').rgb()
        xs = [x for x in range(rect.left(), rect.right())
              for y in range(rect.top(), rect.bottom())
              if image.pixel(x, y) == yellow]
        assert xs, 'note icon was not painted'
        name_width = tree.fontMetrics().horizontalAdvance(item.text(0))
        assert min(xs) > rect.left() + name_width
        tree.hide()

    def test_size_hint_leaves_room_for_icons(self, tree):
        from qtpy.QtWidgets import QStyleOptionViewItem
        item = self._leaf_item(tree)
        index = tree.indexFromItem(item, 0)
        delegate = tree.itemDelegateForColumn(0)
        option = QStyleOptionViewItem()
        before = delegate.sizeHint(option, index).width()
        self._node(tree).problem = 'boom'
        self._node(tree).item.set_note('x')
        tree.populate_tree()
        item = self._leaf_item(tree)
        index = tree.indexFromItem(item, 0)
        assert self._marks(item) == ['other', 'note']
        assert delegate.sizeHint(option, index).width() >= before + 2 * 16
