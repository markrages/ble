#!/usr/bin/python

import ble
import uuids

class BodySensorLocation(ble.Characteristic):
    uuid = uuids.body_sensor_location
    
    @property
    def value(self):
        return self.interpret_raw_body_sensor_location(self.raw)
        
    def interpret_raw_body_sensor_location(self, raw_value):
        value = [ord(c) for c in raw_value]
        
        location = ['Other',
                    'Chest',
                    'Wrist',
                    'Finger',
                    'Hand',
                    'Ear Lobe',
                    'Foot'][value[0]]

        return {'location':location}
