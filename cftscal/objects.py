'''
`CalibratedObject` is a named object that can have one or more calibrations
(e.g., as we recalibrate over time) associated with it. Since we may have
multiple calibration systems (e.g., the EPL CFTS vs cftscal), each
`CalibratedObject` can have one or more subclasses of `CalibrationLoader`
registered. Each `CalibrationLoader` will provide a list of calibrations for
that object that were done with that calibration system.
'''
import datetime as dt
from functools import cached_property, total_ordering
import importlib
import json
import os
from pathlib import Path
import re

import numpy as np
import pandas as pd

from psiaudio.calibration import FlatCalibration, InterpCalibration
from psiaudio import util

from psidata.api import Recording
from cftsdata.api import InearCalibration, MicrophoneCalibration

from . import CAL_ROOT


@total_ordering
class Calibration:
    '''
    Defines the methods that need to be stubbed out for a Calibration and
    implements some specail methods to enable ordering, hashing, and converting
    to/from string for inter-process communication.
    '''
    def load(self):
        raise NotImplementedError

    def datetime(self):
        raise NotImplementedError

    def load(self):
        raise NotImplementedError

    def __repr__(self):
        return f'Calibration :: {self.name} ({self.datetime} - {self.label})'

    def _get_cmp_key(self, obj):
        if obj is None:
            return (None, None, None)
        return obj.name, obj.datetime, obj.label

    def __lt__(self, obj):
        return self._get_cmp_key(self) < self._get_cmp_key(obj)

    def __eq__(self, obj):
        return self._get_cmp_key(self) == self._get_cmp_key(obj)

    def __hash__(self):
        return hash(self._get_cmp_key(self))

    @property
    def label(self):
        return self.__class__.__name__

    @property
    def qualname(self):
        return f'{self.__class__.__module__}.{self.__class__.__name__}'


class FileCalibration(Calibration):

    def __init__(self, name, filename):
        self.name = name
        self.filename = Path(filename)

    def to_string(self):
        return f'{self.qualname}::{self.name}::{self.filename}'

    @classmethod
    def from_string(cls, string):
        _, name, filename = string.split('::')
        return cls(name, filename)


class CFTSFileCalibration(FileCalibration):
    '''
    Base class for CFTS-generated calibrations that store per-recording
    metadata (datetime, sensor names, stimulus, etc.) in a JSON sidecar file
    inside the calibration directory.

    Subclasses expose the individual metadata fields as properties that read
    from ``self.metadata``.  ``self.metadata`` itself is cached, so per-field
    access is a cheap dict lookup.
    '''
    METADATA_FILENAME = 'metadata.json'

    @cached_property
    def metadata(self):
        meta_file = self.filename / self.METADATA_FILENAME
        if not meta_file.exists():
            raise FileNotFoundError(
                f'Missing {self.METADATA_FILENAME} in {self.filename}.\n'
                f'This calibration predates the metadata-sidecar format.\n'
                f'Run `python -m cftscal.migrate_metadata` to generate '
                f'metadata files for existing calibrations.'
            )
        return json.loads(meta_file.read_text())

    @cached_property
    def datetime(self):
        return dt.datetime.fromisoformat(self.metadata['datetime'])


@total_ordering
class CalibratedObject:
    '''
    Represents a calibrated object.

    Parameters
    ----------
    name : str
        Human-readable name of the object (e.g. the microphone or speaker
        name).  Corresponds to the directory that holds this object's
        calibration recordings.
    loaders : list
        CalibrationLoader instances that know how to find this object's
        calibrations.
    folder : str, optional
        Relative path (posix-style) from the loader's ``base_path`` to the
        object's parent directory.  Empty string (the default) means the
        object sits directly under ``base_path``.  Used by the tree view to
        group objects into user-defined lab/study/etc. folders.  Passing
        ``None`` means "no folder filter" — the object aggregates
        calibrations across every folder that has a directory of this name;
        this is the mode used by ``CalibrationManager.get_object`` so
        experiment-side lookups by name remain backwards compatible.
    '''
    def __init__(self, name, loaders, folder=None):
        self.name = name
        self.loaders = loaders
        self.folder = folder

    @property
    def path(self):
        '''
        Fully-qualified identifier: ``folder/name`` when the object lives
        under an organizational folder, or just ``name`` when it sits at
        the loader's storage root.  Two objects with the same name in
        different folders (e.g. ``Lab1/MMM0`` vs ``Lab2/MMM0``) have
        distinct paths and are treated as different calibrated objects.
        '''
        return f'{self.folder}/{self.name}' if self.folder else self.name

    def list_calibrations(self):
        calibrations = []
        for loader in self.loaders:
            calibrations.extend(
                loader.list_calibrations(self.name, folder=self.folder)
            )
        return calibrations

    def get_current_calibration(self):
        return sorted(self.list_calibrations())[-1]

    def __repr__(self):
        return f'{self.__class__.__name__} :: {self.name}'

    def __str__(self):
        return self.name

    def _get_cmp_key(self, obj):
        if obj is None:
            return None
        return (obj.folder or '', obj.name)

    def __lt__(self, obj):
        return self._get_cmp_key(self) < self._get_cmp_key(obj)

    def __eq__(self, obj):
        return self._get_cmp_key(self) == self._get_cmp_key(obj)

    def __hash__(self):
        return hash(self._get_cmp_key(self))


class CalibrationLoader:
    '''
    Provide a list of all calibrated object names and the calibrations
    associated with each object.
    '''

    def list_names(self):
        raise NotImplementedError

    def list_objects(self):
        '''
        Yield ``(folder, name)`` tuples for each calibrated object known to
        this loader.  ``folder`` is a posix-style relative path from the
        loader's storage root; the default implementation yields ``''`` for
        every object (i.e. a flat layout) so legacy loaders that do not
        support nesting continue to work.
        '''
        for name in self.list_names():
            yield '', name

    def list_calibrations(self, name, folder=None):
        '''
        Return calibrations for the object called ``name``.  ``folder`` is
        ignored by the default implementation; loaders that support nested
        folders should filter by it (``None`` means "any folder", ``''``
        means "the loader's root only", any other value means "that specific
        folder path").
        '''
        raise NotImplementedError

    @property
    def label(self):
        return self.__class__.__name__


class CalibrationManager:

    P_NAME = re.compile(r'^(.*)\((.*)\)$')

    def __init__(self, object_class):
        self.loaders = []
        self.object_class = object_class

    def register(self, name):
        module, klass = name.rsplit('.', 1)
        loader = getattr(importlib.import_module(module), klass)()
        self.loaders.append(loader)

    @staticmethod
    def _parse_path(path):
        '''
        Split ``"folder/name"`` into ``(folder, name)``.  A bare ``"name"``
        (no slash) refers to an object at the loader's storage root and
        yields ``('', name)``.
        '''
        folder, sep, name = path.rpartition('/')
        return (folder, name) if sep else ('', path)

    def get_object(self, path):
        '''
        Look up a calibrated object by its full path.

        ``path`` is the value produced by ``list_names`` (and by
        ``CalibratedObject.path``): ``"MMM0"`` for a root-level object,
        ``"Lab1/MMM0"`` for one under an organizational folder.  Two
        objects sharing a name but living in different folders are
        distinct — dropping the folder prefix will only find the root-level
        one (or none, if no such root-level object exists).

        Raises
        ------
        LookupError
            If no loader knows about the requested ``(folder, name)``.  This
            usually means the referenced calibration was moved on disk and
            the user's stored reference is stale — surface the error at
            experiment-launch time so the user updates the reference rather
            than running with no calibration.
        '''
        folder, name = self._parse_path(path)
        loaders = []
        for loader in self.loaders:
            for f, n in loader.list_objects():
                if f == folder and n == name:
                    loaders.append(loader)
                    break
        if not loaders:
            raise LookupError(
                f'No calibrated object at path {path!r}. It may have been '
                f'moved or deleted — check the calibration selected for '
                f'this input/output in your plugin settings.'
            )
        return self.object_class(name, loaders, folder=folder)

    def list_objects(self):
        # One CalibratedObject per (folder, name) so groups in different
        # organizational folders stay visually distinct in the tree view.
        # If several loaders report the same (folder, name) — e.g. an EPL
        # loader and a CFTS loader both know about a starship — they share
        # a single CalibratedObject whose list_calibrations aggregates both.
        keyed = {}
        for loader in self.loaders:
            for folder, name in loader.list_objects():
                keyed.setdefault((folder, name), []).append(loader)
        return [
            self.object_class(name, loaders, folder=folder)
            for (folder, name), loaders in keyed.items()
        ]

    def list_names(self, loader_label=None):
        '''
        Return the fully-qualified paths of every known object.  Root-level
        objects appear as ``"MMM0"``; nested ones as ``"Lab1/MMM0"``.  This
        is what dropdowns should display so the user can pick between two
        objects that share a bare name.
        '''
        def _paths(loader):
            return [
                f'{folder}/{name}' if folder else name
                for folder, name in loader.list_objects()
            ]

        if loader_label is None:
            paths = []
            for loader in self.loaders:
                paths.extend(_paths(loader))
            return paths

        for loader in self.loaders:
            if loader.label == loader_label:
                return _paths(loader)
        else:
            loaders = ', '.join(l.label for l in self.loaders)
            raise ValueError(f'Loader {loader_label} not found. Must be one of {loaders}.')

    def from_string(self, string):
        qualname = string.split('::', 1)[0]
        module_name, class_name = qualname.rsplit('.', 1)
        module = importlib.import_module(module_name)
        klass = getattr(module, class_name)
        return klass.from_string(string)

    def get_property(self, prop_name):
        values = set()
        for obj in self.list_objects():
            for cal in obj.list_calibrations():
                values.add(getattr(cal, prop_name))
        return values


class CFTSBaseLoader(CalibrationLoader):

    def __init__(self):
        self.base_path = CAL_ROOT / self.subfolder
        self.base_path.mkdir(parents=True, exist_ok=True)

    def list_names(self):
        for path in self.base_path.iterdir():
            yield path.stem

    def list_calibrations(self, name, folder=None):
        return [
            self.cal_class(name, cal_dir)
            for (f, n), cal_dirs in self._walk_objects().items()
            if n == name and (folder is None or f == folder)
            for cal_dir in cal_dirs
        ]

    def list_objects(self):
        for folder, name in sorted(self._walk_objects()):
            yield folder, name

    def list_names(self):
        # Keep this returning a flat set of names for backwards compatibility
        # (some callers, e.g. the settings dropdowns, only need the names).
        return sorted({name for _, name in self._walk_objects()})

    def _walk_objects(self):
        '''
        Discover every calibrated object in this loader's storage tree.

        A "calibrated object" is any directory whose immediate children
        include at least one directory containing a ``metadata.json``
        sidecar.  Users can nest object directories arbitrarily deep beneath
        ``self.base_path`` (e.g. to group by lab or study); the returned
        ``folder`` is the posix-style relative path from ``base_path`` to
        the object's parent directory.

        Returns
        -------
        dict
            Maps ``(folder, name)`` to a list of the object's calibration
            directories.
        '''
        objects = {}
        if not self.base_path.exists():
            return objects
        for meta_file in self.base_path.rglob('metadata.json'):
            cal_dir = meta_file.parent
            object_dir = cal_dir.parent
            try:
                rel = object_dir.parent.relative_to(self.base_path)
            except ValueError:
                continue
            folder = '' if str(rel) == '.' else rel.as_posix()
            objects.setdefault((folder, object_dir.name), []).append(cal_dir)
        return objects


################################################################################
# Special calibration objects
################################################################################
class UnityInputCalibration(Calibration):

    def load(self):
        return FlatCalibration.unity()

    def to_string(self):
        return self.qualname

    @classmethod
    def from_string(cls, string):
        return cls()


class UnityInputCalibrationLoader(CalibrationLoader):

    def list_names(self):
        return ['unity']

    def list_calibrations(self, name, folder=None):
        return [UnityInputCalibration()]


################################################################################
# Starship calibration management
################################################################################
class Starship(CalibratedObject):
    pass


class EPLStarshipCalibration(FileCalibration):
    '''
    Wrapper around a probe tube calibration file generated by the EPL CFTS
    calibration program.
    '''

    def _get_cmp_key(self, obj):
        if obj is None:
            return (None, None, None, None)
        return obj.name, obj.datetime, obj.smoothed, obj.label

    @cached_property
    def datetime(self):
        with self.filename.open() as fh:
            for line in fh:
                if line.startswith('Date: '):
                    break
        return dt.datetime.strptime(line[6:].strip(), '%m/%d/%Y %I:%M:%S %p')

    @cached_property
    def smoothed(self):
        with self.filename.open() as fh:
            for line in fh:
                if line.startswith('[Smoothing]'):
                    return True
                if line.startswith('Freq(Hz)'):
                    return False

    def load(self):
        attrs ={
            'calibration_file': str(self.filename),
            'name': self.name,
            'string': self.to_string(),
            'class': self.qualname,
        }
        with self.filename.open() as fh:
            for line in fh:
                if line.startswith('Freq(Hz)'):
                    break
            cal = pd.read_csv(fh, sep='\t', header=None)
            return InterpCalibration.from_spl(cal[0], cal[1], attrs=attrs)

    def __repr__(self):
        s = 'smoothed' if self.smoothed else 'raw'
        return f'Calibration :: {self.name} ({self.datetime} {s} - {self.label})'


class EPLStarshipLoader(CalibrationLoader):
    '''
    Interface that lists available starships and calibrations generated by the
    EPL CFTS calibration program.
    '''
    base_path = Path(r'C:\Data\Probe Tube Calibrations')

    def list_names(self):
        names = set()
        for calfile in self.base_path.glob('*_ProbeTube*.calib'):

            name = calfile.stem.rsplit('.', 1)[0].rsplit('_', 1)[0]
            names.add(f'{name} (EPL)')
        return names

    def list_calibrations(self, name, folder=None):
        if name.endswith(' (EPL)'):
            name, _ = name.rsplit(' ', 1)
        calibrations = []
        for filename in self.base_path.glob(f'{name}_ProbeTube*.calib'):
            calibration = EPLStarshipCalibration(name, filename)
            calibrations.append(calibration)
        return calibrations


class CFTSStarshipCalibration(CFTSFileCalibration):
    '''
    Wrapper around a probe tube calibration file generated by the
    psiexperiment-based CFTS calibration program.
    '''

    @property
    def microphone(self):
        return self.metadata['microphone']

    @property
    def coupler(self):
        return self.metadata['coupler']

    @property
    def stimulus(self):
        return self.metadata['stimulus']

    def load(self):
        if self.stimulus == 'golay':
            return self.load_golay()
        elif self.stimulus == 'chirp':
            return self.load_chirp()

    def load_chirp(self):
        index_col = ['hw_ao_chirp_level', 'frequency']
        sens = pd.read_csv(self.filename / 'chirp_sens.csv', index_col=index_col)
        output_gain = float(sens.index.unique('hw_ao_chirp_level').max())
        s = sens.loc[output_gain]
        attrs ={
            'calibration_file': str(self.filename),
            'name': self.name,
            'string': self.to_string(),
            'class': self.qualname,
            'output_gain': output_gain,
        }
        return InterpCalibration(s.index.values, s['sens'].values, attrs=attrs)

    def load_golay(self):
        index_col = ['n_bits', 'output_gain', 'frequency']
        sens = pd.read_csv(self.filename / 'golay_sens.csv', index_col=index_col)
        n_bits = int(sens.index.unique('n_bits').max())
        output_gain = float(sens.index.unique('output_gain').max())
        s = sens.loc[n_bits, output_gain]
        attrs ={
            'calibration_file': str(self.filename),
            'name': self.name,
            'string': self.to_string(),
            'class': self.qualname,
            'n_bits': n_bits,
            'output_gain': output_gain,
        }
        return InterpCalibration(s.index.values, s['sens'].values, attrs=attrs)


class CFTSStarshipLoader(CFTSBaseLoader):
    subfolder = 'starship'
    cal_class = CFTSStarshipCalibration


################################################################################
# Speaker calibration management
################################################################################
class Output(CalibratedObject):
    '''
    Base class for all inputs.
    '''
    pass


class Speaker(Output):
    '''
    Base class for all speakers.
    '''
    pass


class CFTSSpeakerCalibration(CFTSFileCalibration):
    '''
    Wrapper around a speaker calibration file generated by the
    psiexperiment-based CFTS calibration program.
    '''

    @property
    def microphone(self):
        return self.metadata['microphone']

    @property
    def method(self):
        return self.metadata['method']

    @cached_property
    def max_frequency(self):
        return self.sens.index.unique('frequency').max()

    @cached_property
    def n_bits(self):
        return int(self.sens.index.unique('n_bits').max())

    @cached_property
    def output_gain(self):
        return float(self.sens.index.unique('output_gain').max())

    @cached_property
    def sens(self):
        index_col = ['n_bits', 'output_gain', 'frequency']
        return pd.read_csv(self.filename / 'golay_sens.csv', index_col=index_col)

    def load(self):
        s = self.sens.loc[self.n_bits, self.output_gain]
        attrs = {
            'calibration_file': str(self.filename),
            'name': self.name,
            'string': self.to_string(),
            'class': self.qualname,
            'n_bits': self.n_bits,
            'output_gain': self.output_gain,
        }
        return InterpCalibration(s.index.values, s['sens'].values, attrs=attrs)


class CFTSSpeakerLoader(CFTSBaseLoader):
    subfolder = 'speaker'
    cal_class = CFTSSpeakerCalibration


################################################################################
# Amplifier calibration management
################################################################################
class InputAmplifier(CalibratedObject):
    pass


class CFTSInputAmplifierCalibration(CFTSFileCalibration):

    @cached_property
    def measured_gain(self):
        sens_file = self.filename / 'amplifier_gain.json'
        gain = json.loads(sens_file.read_text())
        return gain['gain mean (linear)']

    def load_recording(self):
        return Recording(self.filename)


class CFTSInputAmplifierLoader(CFTSBaseLoader):
    subfolder = 'input_amplifier'
    cal_class = CFTSInputAmplifierCalibration


################################################################################
# Microphone calibration management
################################################################################
class Input(CalibratedObject):
    '''
    Base class for all inputs.
    '''
    pass


class Microphone(Input):
    '''
    Base class for all microphones.
    '''
    pass


class GenericMicrophone(Microphone):
    '''
    Defines a microphone that may not have a flat frequency response (e.g.,
    such as for use in monitoring ambient sound in chamber).
    '''
    pass


class MeasurementMicrophone(GenericMicrophone):
    '''
    Defines a microphone that has a flat frequency response and can be
    calibrated using a pistonphone at a single frequency.
    '''
    pass


class CFTSMicrophoneCalibration(CFTSFileCalibration):
    pass


class CFTSMeasurementMicrophoneCalibration(CFTSMicrophoneCalibration):

    @property
    def pistonphone(self):
        return self.metadata['pistonphone']

    @property
    def sensor_id(self):
        # Physical-device identifier (e.g. serial number).  Free-form
        # metadata for tracking which unit was used; not part of the
        # calibration's lookup identity.  Falls back to the legacy
        # ``sensor`` key so calibrations recorded during the brief window
        # when that field was named differently still render.
        return self.metadata.get('sensor_id', self.metadata.get('sensor', ''))

    @property
    def gain(self):
        return self.metadata.get('gain', 0)

    @property
    def input_channel(self):
        # IO-manifest input name (e.g. "microphone_1", "ai0") the
        # calibration was recorded on.  Old calibrations without this
        # metadata render as ''.
        return self.metadata.get('input_channel', '')

    @cached_property
    def sens(self):
        try:
            sens_file = self.filename / 'microphone_sensitivity.json'
            cal = json.loads(sens_file.read_text())
            return cal['mic sens overall (mV/Pa)']
        except:
            return np.nan

    @cached_property
    def sens_db(self):
        return util.db(self.sens)

    def load(self):
        sens_file = self.filename / 'microphone_sensitivity.json'
        cal = json.loads(sens_file.read_text())
        sens = cal['mic sens overall (mV/Pa)']
        attrs = {
            'name': self.name,
            'calibration_file': str(self.filename),
            'calibration': cal,
            'string': self.to_string(),
            'class': self.qualname,
        }
        return FlatCalibration.from_mv_pa(sens, attrs=attrs)

    def load_recording(self):
        return MicrophoneCalibration(self.filename)


class CFTSGenericMicrophoneCalibration(CFTSMicrophoneCalibration):

    @property
    def measurement_microphone(self):
        return self.metadata['measurement_microphone']

    @property
    def stimulus(self):
        return self.metadata['stimulus']

    @cached_property
    def max_frequency(self):
        return self.sens.index.unique('frequency').max()

    @cached_property
    def n_bits(self):
        return int(self.sens.index.unique('n_bits').max())

    @cached_property
    def output_gain(self):
        return float(self.sens.index.unique('output_gain').max())

    @cached_property
    def sens(self):
        index_col = ['n_bits', 'output_gain', 'frequency']
        return pd.read_csv(self.filename / 'golay_sens.csv', index_col=index_col)

    def load(self):
        '''
        Load calibration that was run at the highest output gain and number of
        bits under the assumption that this represents the calibration with the
        highest SNR and resolution.
        '''
        s = self.sens.loc[self.n_bits, self.output_gain]
        attrs ={
            'calibration_file': str(self.filename),
            'name': self.name,
            'string': self.to_string(),
            'class': self.qualname,
            'n_bits': self.n_bits,
            'output_gain': self.output_gain,
        }
        return InterpCalibration(s.index.values, s['sens'].values,
                                 reference='SPL', attrs=attrs)


class CFTSMeasurementMicrophoneLoader(CFTSBaseLoader):

    subfolder = 'microphone'
    cal_class = CFTSMeasurementMicrophoneCalibration


class CFTSGenericMicrophoneLoader(CFTSBaseLoader):

    subfolder = 'microphone_generic'
    cal_class = CFTSGenericMicrophoneCalibration


################################################################################
# Managing input recordings
################################################################################
class InputRecording(CalibratedObject):
    '''
    Base class for all input devices.
    '''
    pass


class CFTSInputRecording(CFTSFileCalibration):
    '''
    Input monitor recording created by CFTS
    '''

    @property
    def generator(self):
        return self.metadata['generator']

    @property
    def sensors(self):
        '''
        Mapping of recorded channel name -> ``{'label': ..., 'sensor': ...}``.

        ``label`` is the human-readable channel label shown in the
        Settings panel's dropdown (e.g. "Ch 2") -- what tables should
        display -- while the key itself is the real hardware channel
        name (e.g. "ai2"), needed to look up the recorded signal via
        ``getattr(recording, channel)``. ``sensor`` is the calibration
        name of the sensor that was attached to that channel.

        Recordings made before multi-channel support used a singular
        `sensor` key and always recorded exactly one channel under the
        fixed array name `selected_input` (see the pre-multi-channel
        `Input` manifest in cftscal/paradigms/objects.enaml). No real
        channel label was ever recorded for these, so `label` falls
        back to the synthesized channel name itself. Synthesizing the
        equivalent single-entry dict here lets `.load()`-based code
        (InputRecordingPlotManager, export_calibration) treat old and
        new recordings identically via `self.sensors.items()`.
        '''
        if 'sensors' in self.metadata:
            return self.metadata['sensors']
        return {
            'selected_input': {
                'label': 'selected_input',
                'sensor': self.metadata['sensor'],
            },
        }

    def load(self):
        return Recording(self.filename)


class CFTSInputRecordingLoader(CFTSBaseLoader):

    subfolder = 'input-recording'
    cal_class = CFTSInputRecording


################################################################################
# InEar calibration management
################################################################################
class InEar(CalibratedObject):
    pass


class CFTSInEarCalibration(CFTSFileCalibration):

    @property
    def starship(self):
        return self.metadata['starship']

    @property
    def ear(self):
        return self.metadata['ear']

    def load_recording(self):
        return InearCalibration(self.filename)

    def load(self):
        index_col = ['hw_ao_chirp_level', 'frequency']
        sens = pd.read_csv(self.filename / 'chirp_sens.csv', index_col=index_col)
        level = int(sens.index.unique('hw_ao_chirp_level').max())
        s = sens.loc[level]
        attrs ={
            'calibration_file': str(self.filename),
            'name': self.name,
            'string': self.to_string(),
            'class': self.qualname,
            'level': level,
        }
        return InterpCalibration(s.index.values, s['norm_spl'].values, attrs=attrs)


class CFTSInEarLoader(CFTSBaseLoader):
    subfolder = 'inear'
    cal_class = CFTSInEarCalibration

    def _walk_objects(self):
        '''
        Discover in-ear calibrations grouped by starship, reading identity
        from ``metadata.json`` rather than parsing filename segments.

        In-ear calibrations traditionally live at
        ``inear/<ear>/<cal>/metadata.json`` — the on-disk parent of the
        calibration is the ear (e.g., ``left``, ``right``), and the
        starship name comes from the metadata sidecar.  This override
        treats the starship as the object identity (matching the other
        CFTS loaders' one-object-per-name model) and uses whatever sits
        between the loader's ``base_path`` and the calibration directory
        as the organizational folder — typically the ear, but any nested
        org folders added via drag-drop or the group_path picker are
        preserved.
        '''
        objects = {}
        if not self.base_path.exists():
            return objects
        for meta_file in self.base_path.rglob('metadata.json'):
            cal_dir = meta_file.parent
            try:
                metadata = json.loads(meta_file.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            starship = metadata.get('starship')
            if not starship:
                continue
            try:
                rel = cal_dir.parent.relative_to(self.base_path)
            except ValueError:
                continue
            folder = '' if str(rel) == '.' else rel.as_posix()
            objects.setdefault((folder, starship), []).append(cal_dir)
        return objects


################################################################################
# Basic cal registration
################################################################################
# Only measurement microphones
measurement_microphone_manager = CalibrationManager(MeasurementMicrophone)
measurement_microphone_manager.register('cftscal.objects.CFTSMeasurementMicrophoneLoader')

# Only generic microphones
generic_microphone_manager = CalibrationManager(GenericMicrophone)
generic_microphone_manager.register('cftscal.objects.CFTSGenericMicrophoneLoader')

# All microphones
microphone_manager = CalibrationManager(GenericMicrophone)
microphone_manager.register('cftscal.objects.CFTSGenericMicrophoneLoader')
microphone_manager.register('cftscal.objects.CFTSMeasurementMicrophoneLoader')

# All inputs including passthrough inputs
input_manager = CalibrationManager(Input)
input_manager.register('cftscal.objects.CFTSGenericMicrophoneLoader')
input_manager.register('cftscal.objects.CFTSMeasurementMicrophoneLoader')
input_manager.register('cftscal.objects.UnityInputCalibrationLoader')

# All outputs. Eventually we may add more outputs and/or incorporate some sort
# of passthrough output (e.g., unity/attenuation).
output_manager = CalibrationManager(Output)
output_manager.register('cftscal.objects.CFTSSpeakerLoader')

speaker_manager = CalibrationManager(Speaker)
speaker_manager.register('cftscal.objects.CFTSSpeakerLoader')

# The following items need to be examined to see if they should subclass Input/Output
input_amplifier_manager = CalibrationManager(InputAmplifier)
input_amplifier_manager.register('cftscal.objects.CFTSInputAmplifierLoader')

input_recording_manager = CalibrationManager(InputRecording)
input_recording_manager.register('cftscal.objects.CFTSInputRecordingLoader')

inear_manager = CalibrationManager(InEar)
inear_manager.register('cftscal.objects.CFTSInEarLoader')

starship_manager = CalibrationManager(Starship)
starship_manager.register('cftscal.objects.EPLStarshipLoader')
starship_manager.register('cftscal.objects.CFTSStarshipLoader')


def show_objects(show_calibrations):

    def printer(d):
        for loader in d.loaders:
            print(f'  - {loader.label}')
            for name in sorted(d.list_names(loader.label)):
                print(f'    . {name}')
                if show_calibrations:
                    o = d.get_object(name)
                    for calibration in o.list_calibrations():
                        print(f'        {calibration}')

    print('Looking for calibrated objects')

    print('* Input Recordings')
    printer(input_recording_manager)

    print('* Starships')
    printer(starship_manager)

    print('* Measurement Microphones')
    printer(measurement_microphone_manager)

    print('* Generic Microphones')
    printer(generic_microphone_manager)

    print('* Inear')
    printer(inear_manager)


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('--show-calibrations', action='store_true')
    args = parser.parse_args()
    show_objects(args.show_calibrations)
