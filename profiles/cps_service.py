#!/usr/bin/python

import ble
import uuids

OPCODE_START_CALIBRATION=12
OPCODE_SET_CPM_MASK=13

RESPONSE_VALUE_SUCCESS=1

OPCODE_NOT_SUPPORTED=2
class OpcodeNotSupported(Exception): pass

INVALID_PARAMETER=3
class InvalidParameter(Exception): pass

OPERATION_FAILED=4
class OperationFailed(Exception): pass

class CyclingPowerService(ble.Service):
    uuid=uuids.cycling_power
    
    def calibrate(self):
        cp = self.cycling_power_control_point
        
        cp.notifying=True
        resp = cp.write_opcode(OPCODE_START_CALIBRATION)
        assert(resp[0]==0x20) # control response
        assert(resp[1]==OPCODE_START_CALIBRATION)
        response_value = resp[2]
        cp.check_fail(response_value)

        raw_value = resp[3]+256*resp[4]
        if raw_value > 0x7fff:
            raw_value -= 0x10000
        return {"nm32":raw_value,"Nm":raw_value/32.}

    def set_reported_features(self, mask):
        cp = self.cycling_power_control_point
        
        cp.notifying=True
        resp = cp.write_opcode(OPCODE_SET_CPM_MASK,[mask & 0xff, mask >> 8])
        assert(resp[0]==0x20) # control response
        assert(resp[1]==OPCODE_SET_CPM_MASK)
        response_value = resp[2]
        cp.check_fail(response_value)
         
class CyclingPowerControlPoint(ble.Characteristic):
    uuid=uuids.cycling_power_control_point

    def check_fail(self, response):
        if response==RESPONSE_VALUE_SUCCESS: return True
        elif response==OPCODE_NOT_SUPPORTED: raise OpcodeNotSupported
        elif response==INVALID_PARAMETER: raise InvalidParameter
        elif response==OPERATION_FAILED: raise OperationFailed
        else: raise UnknownResponseError

    def write_opcode(self, 
                     opcode,
                     data=None,
                     timeout=30, # seconds
                 ):
        data = data or []
        self.notify_timeout=timeout
        self.value = [opcode]+data
        return self.value

class CyclingPowerMeasurement(ble.Characteristic):
    uuid=uuids.cycling_power_measurement

    @property
    def value(self):
        return self.interpret_raw_cpm_measurement(self.raw)

    def interpret_raw_cpm_measurement(self, raw_value):
        
        value = [ord(c) for c in raw_value]

        flags = value.pop(0)
        flags += value.pop(0)<<8

        flag_names = [
          ('Pedal Power Balance Present',(False,True)),
          ('Pedal Power Balance Reference',('Unknown','Left')),
          ('Accumulated Torque Present',(False,True)),
          ('Accumulated Torque Source',('Wheel Based','Crank Based')),
          ('Wheel Revolution Data Present',(False,True)),
          ('Crank Revolution Data Present',(False,True)),
          ('Extreme Force Magnitudes Present',(False,True)),
          ('Extreme Torque Magnitudes Present',(False,True)),
          ('Extreme Angles Present',(False,True)),
          ('Top Dead Spot Angle Present',(False,True)),
          ('Bottom Dead Spot Angle Present',(False,True)),
          ('Accumulated Energy Present',(False,True)),
          ('Offset Compensation Indicator',(False,True)),
        ]

        meas={'flags':flags}
        for i,(name,choice) in enumerate(flag_names):
          meas[name]=choice[bool(flags & (1<<i))]

        power = value.pop(0)
        power += value.pop(0)<<8

        if power > 0x7fff: power -= 0x8000

        meas['watts']=power

        if meas['Pedal Power Balance Present']:
          balance = value.pop(0)
          if balance > 127: balance -= 256
          balance /= 2.0
          meas['power_balance']=balance

        if meas['Accumulated Torque Present']:
          accum_torque = value.pop(0)
          accum_torque = value.pop(0)<<8
          accum_torque /= 32.0
          meas['accum_torque']=accum_torque

        if meas['Wheel Revolution Data Present']:
          wheel_revs = value.pop(0)
          wheel_revs += value.pop(0)<<8
          wheel_revs += value.pop(0)<<16
          wheel_revs += value.pop(0)<<24

          wheel_time = value.pop(0)
          wheel_time += value.pop(0)<<8

          meas['wheel_revs'] = wheel_revs
          meas['wheel_time'] = wheel_time

        if meas['Crank Revolution Data Present']:
          crank_revs = value.pop(0)
          crank_revs += value.pop(0)<<8

          crank_time = value.pop(0)
          crank_time += value.pop(0)<<8

          meas['crank_revs'] = crank_revs
          meas['crank_time'] = crank_time

        assert(not meas['Extreme Force Magnitudes Present'])
        assert(not meas['Extreme Torque Magnitudes Present'])
        assert(not meas['Extreme Angles Present'])
        assert(not meas['Top Dead Spot Angle Present'])
        assert(not meas['Bottom Dead Spot Angle Present'])

        if meas['Accumulated Energy Present']:
          accum_j = value.pop(0)
          accum_j += value.pop(0)<<8
          accum_j *= 1000
          meas['joules'] = accum_j

        return meas

class CyclingPowerVector(ble.Characteristic):
    uuid=uuids.cycling_power_vector

    @property
    def value(self):
        return self.interpret_raw_cpv_measurement(self.raw)

    def interpret_raw_cpv_measurement(self, raw_value):
        
        value = [ord(c) for c in raw_value]

        flags = value.pop(0)

        flag_names = [
            ('Crank Revolution Data Present',(False, True)),
            ('First Crank Measurement Angle Present',(False, True)),
            ('Instant Force Magnitude Array Present',(False, True)),
            ('Instant Torque Magnitude Array Present',(False, True)),
        ]

        meas={'flags':flags}
        for i,(name,choice) in enumerate(flag_names):
          meas[name]=choice[bool(flags & (1<<i))]

        meas['Measurement Direction']=['Unknown',
                                       'Tangential Component',
                                       'Radial Component',
                                       'Lateral Component'][(flags >> 4)&3]

        if meas['Crank Revolution Data Present']:
            revs = value.pop(0)
            revs += 256*value.pop(0)
            
            crank_time = value.pop(0)
            crank_time += 256*value.pop(0)
            
            meas['crank_revs']=revs
            meas['crank_time']=crank_time/1024.

        if meas['First Crank Measurement Angle Present']:
            angle = value.pop(0)
            angle += 256*value.pop(0)
            meas['first_angle'] = angle
            
        if meas['Instant Force Magnitude Array Present']:
            forces=[]
            while value:
                force = value.pop(0)
                force += 256*value.pop(0)
                if force > 0x8000:
                    force -= 0x10000
                forces.append(force)
            meas['force_array']=forces

        if meas['Instant Torque Magnitude Array Present']:
            torques=[]
            while value:
                torque = value.pop(0)
                torque += 256*value.pop(0)
                if torque > 0x8000:
                    torque -= 0x10000
                torques.append(torque)
            meas['torque_array']=torques

        return meas
