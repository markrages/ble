#!/usr/bin/python

import ble
import uuids

OPCODE_RESET_EXPENDED=1

class HeartRateService(ble.Service):
    uuid=uuids.heart_rate
             
class HeartRateControlPoint(ble.Characteristic):
    uuid=uuids.heart_rate_control_point

    def reset_expended(self):
        opcode = OPCODE_RESET_EXPENDED
        self.value = [opcode]

class HeartRateMeasurement(ble.Characteristic):
    uuid=uuids.heart_rate_measurement

    @property
    def value(self):
        return self.interpret_raw_hrm_measurement(self.raw)

    def interpret_raw_hrm_measurement(self, raw_value):
        
        value = [ord(c) for c in raw_value]

        flags = value.pop(0)
        
        hr_format = (flags>>0) & 1;
        contact_status = (flags>>1) & 3;
        expended_present = (flags>>3) & 1;
        rr_present = (flags>>4) & 1;

        meas={}

        meas['hr'] = value.pop(0)
        if (hr_format):
            meas['hr'] += 256*value.pop(0)

        if (contact_status & 2):
            meas['sensor_contact'] = bool(contact_status & 1)

        if expended_present:
            e = value.pop(0)
            e += 256*value.pop(0)
            meas['energy_expended'] = e

        if rr_present:
            rr = []
            while value:
                rr_val = value.pop(0)
                rr_val += 256*value.pop(0)
                rr_val /= 1024.
                rr.append(rr_val)
            meas['rr'] = rr

        return meas

