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

    def to_string(self):
        return f'{self.qualname}::{self.name}::{self.filename}'

    @classmethod
    def from_string(cls, string):
        _, name, filename = string.split('::')
        return cls(name, filename)

    def datetime(self):
        raise NotImplementedError

    def load(self):
        raise NotImplementedError


@total_ordering
class CalibratedObject:

    def __init__(self, name, loaders):
        self.name = name
        self.loaders = loaders

    def list_calibrations(self):
        calibrations = []
        for loader in self.loaders:
            calibrations.extend(loader.list_calibrations(self.name))
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
        return obj.name

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

    def list_calibrations(self, name):
        raise NotImplementedError


class CalibrationManager:

    P_NAME = re.compile(r'^(.*)\((.*)\)$')

    def __init__(self, object_class):
        self.loaders = []
        self.object_class = object_class

    def register(self, name):
        module, klass = name.rsplit('.', 1)
        loader = getattr(importlib.import_module(module), klass)()
        self.loaders.append(loader)

    def get_object(self, name):
        return self.object_class(name, self.loaders)

    def list_objects(self):
        names = {}
        for loader in self.loaders:
            for name in loader.list_names():
                names.setdefault(name, []).append(loader)
        objects = []
        for name, loaders in names.items():
            objects.append(self.object_class(name, loaders))
        return objects

    def list_names(self, loader_label=None):
        if loader_label is None:
            names = []
            for loader in self.loaders:
                names.extend(loader.list_names())
            return names

        for loader in self.loaders:
            if loader.label == loader_label:
                return loader.list_names()
        else:
            raise ValueError('Loader {loader_label} not found')

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
        self.label = 'CFTS'
        self.base_path = CAL_ROOT / self.subfolder
        self.base_path.mkdir(parents=True, exist_ok=True)

    def list_names(self):
        for path in self.base_path.iterdir():
            yield path.stem

    def list_calibrations(self, name):
        calibrations = []
        for path in (self.base_path / name).glob(f'*_{name}_*'):
            calibrations.append(self.cal_class(name, path))
        return calibrations


################################################################################
# Starship calibration management
################################################################################
class Starship(CalibratedObject):
    pass


class EPLStarshipCalibration(Calibration):
    '''
    Wrapper around a probe tube calibration file generated by the EPL CFTS
    calibration program.
    '''
    def __init__(self, name, filename):
        self.label = 'EPL'
        self.name = name
        self.filename = Path(filename)
        self.qualname = f'{self.__class__.__module__}.{self.__class__.__name__}'

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
    label = 'EPL'
    base_path = Path(r'C:\Data\Probe Tube Calibrations')

    def list_names(self):
        names = set()
        for calfile in self.base_path.glob('*_ProbeTube*.calib'):

            name = calfile.stem.rsplit('.', 1)[0].rsplit('_', 1)[0]
            names.add(f'{name} (EPL)')
        return names

    def list_calibrations(self, name):
        if name.endswith(' (EPL)'):
            name, _ = name.rsplit(' ', 1)
        calibrations = []
        for filename in self.base_path.glob(f'{name}_ProbeTube*.calib'):
            calibration = EPLStarshipCalibration(name, filename)
            calibrations.append(calibration)
        return calibrations


class CFTSStarshipCalibration(Calibration):
    '''
    Wrapper around a probe tube calibration file generated by the
    psiexperiment-based CFTS calibration program.
    '''
    def __init__(self, name, filename):
        self.label = 'CFTS'
        self.name = name
        self.filename = Path(filename)
        self.qualname = f'{self.__class__.__module__}.{self.__class__.__name__}'

    @cached_property
    def datetime(self):
        datestr, _ = self.filename.stem.split('_', 1)
        return dt.datetime.strptime(datestr, '%Y%m%d-%H%M%S')

    @cached_property
    def microphone(self):
        return self.filename.stem.split('_')[2]

    @cached_property
    def coupler(self):
        return self.filename.stem.split('_')[3]

    @cached_property
    def stimulus(self):
        return self.filename.stem.split('_')[-1]

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
class Speaker(CalibratedObject):
    pass


class CFTSSpeakerCalibration(Calibration):
    '''
    Wrapper around a speaker calibration file generated by the
    psiexperiment-based CFTS calibration program.
    '''
    def __init__(self, name, filename):
        self.label = 'CFTS'
        self.name = name
        self.filename = Path(filename)
        self.qualname = f'{self.__class__.__module__}.{self.__class__.__name__}'

    @cached_property
    def datetime(self):
        datestr, _ = self.filename.stem.split('_', 1)
        return dt.datetime.strptime(datestr, '%Y%m%d-%H%M%S')

    @cached_property
    def microphone(self):
        return self.filename.stem.split('_')[2]

    @cached_property
    def method(self):
        return self.filename.stem.split('_')[3]

    def load(self):
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


class CFTSSpeakerLoader(CFTSBaseLoader):
    subfolder = 'speaker'
    cal_class = CFTSSpeakerCalibration


################################################################################
# Amplifier calibration management
################################################################################
class InputAmplifier(CalibratedObject):
    pass


class CFTSInputAmplifierCalibration(Calibration):

    def __init__(self, name, filename):
        self.label = 'CFTS'
        self.name = name
        self.filename = Path(filename)
        self.qualname = f'{self.__class__.__module__}.{self.__class__.__name__}'

    @cached_property
    def datetime(self):
        datestr, _ = self.filename.stem.split('_', 1)
        return dt.datetime.strptime(datestr, '%Y%m%d-%H%M%S')

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
class Microphone(CalibratedObject):
    pass


class CFTSMicrophoneCalibration(Calibration):

    def __init__(self, name, filename):
        self.label = 'CFTS'
        self.name = name
        self.filename = Path(filename)
        self.qualname = f'{self.__class__.__module__}.{self.__class__.__name__}'

    @cached_property
    def pistonphone(self):
        return self.filename.stem.rsplit('_', 1)[1]

    @cached_property
    def datetime(self):
        datestr, _ = self.filename.stem.split('_', 1)
        return dt.datetime.strptime(datestr, '%Y%m%d-%H%M%S')

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


class CFTSMicrophoneLoader(CFTSBaseLoader):
    subfolder = 'microphone'
    cal_class = CFTSMicrophoneCalibration


################################################################################
# InEar calibration management
################################################################################
class InEar(CalibratedObject):
    pass


class CFTSInEarCalibration(Calibration):

    def __init__(self, name, filename):
        self.label = 'CFTS'
        self.name = name
        self.filename = Path(filename)
        self.qualname = f'{self.__class__.__module__}.{self.__class__.__name__}'

    @cached_property
    def starship(self):
        return self.filename.stem.rsplit('_', 1)[1]

    @cached_property
    def ear(self):
        return self.filename.stem.split('_', 2)[1]

    @cached_property
    def datetime(self):
        datestr, _ = self.filename.stem.split('_', 1)
        return dt.datetime.strptime(datestr, '%Y%m%d-%H%M%S')

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

    def list_names(self):
        self.names = {}
        for path in self.base_path.iterdir():
            for subpath in path.iterdir():
                name = subpath.stem.rsplit('_', 1)[1]
                cal = self.cal_class(name, subpath)
                self.names.setdefault(name, []).append(cal)
        for name in sorted(self.names.keys()):
            yield name

    def list_calibrations(self, name):
        return self.names[name]


################################################################################
# Basic cal registration
################################################################################
input_amplifier_manager = CalibrationManager(InputAmplifier)
input_amplifier_manager.register('cftscal.objects.CFTSInputAmplifierLoader')

microphone_manager = CalibrationManager(Microphone)
microphone_manager.register('cftscal.objects.CFTSMicrophoneLoader')

starship_manager = CalibrationManager(Starship)
starship_manager.register('cftscal.objects.EPLStarshipLoader')
starship_manager.register('cftscal.objects.CFTSStarshipLoader')

speaker_manager = CalibrationManager(Speaker)
speaker_manager.register('cftscal.objects.CFTSSpeakerLoader')

inear_manager = CalibrationManager(InEar)
inear_manager.register('cftscal.objects.CFTSInEarLoader')


def show_objects():
    print('Looking for objects')
    print('Microphones')
    for name in microphone_manager.list_names():
        print(' * name')


if __name__ == '__main__':
    show_objects()
