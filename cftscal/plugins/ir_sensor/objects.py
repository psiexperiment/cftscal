import datetime as dt
from functools import cached_property
import json
from pathlib import Path

from psidata.api import Recording

from cftscal.objects import (
    CalibrationManager, CFTSBaseLoader, FileCalibration, InputRecording
)


class IRSensor(InputRecording):
    pass


class CFTSIRSensorRecording(FileCalibration):
    '''
    IR sensor recording created by CFTS
    '''
    @cached_property
    def sens(self):
        sens_file = self.filename / 'sensitivity.json'
        return json.loads(sens_file.read_text())

    @cached_property
    def v_min(self):
        return self.sens['lower']

    @cached_property
    def v_max(self):
        return self.sens['upper']

    @cached_property
    def datetime(self):
        datestr = self.filename.stem.split('_')[0]
        return dt.datetime.strptime(datestr, '%Y%m%d-%H%M%S')

    @cached_property
    def input_channel(self):
        return self.filename.stem.split('_')[1]

    def load(self):
        return Recording(self.filename)


class CFTSIRSensorLoader(CFTSBaseLoader):

    subfolder = 'ir-sensor'
    cal_class = CFTSIRSensorRecording


manager = CalibrationManager(IRSensor)
manager.register('cftscal.plugins.ir_sensor.objects.CFTSIRSensorLoader')
