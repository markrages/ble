#!/usr/bin/python

import ble
import os

device_name = os.getenv('BLE_DEVICE_NAME') or 'CATEYE_HRM'

try:
    dev = ble.discover_device(lambda d: d['Name'] == device_name)
    dev.connect()

    print "Location",dev.heart_rate_service.body_sensor_location.value
    print "battery level",dev.battery_service.battery_level.value

    dev.heart_rate_service.heart_rate_measurement.notifying=True
    for i in range(10):
        print dev.heart_rate_service.heart_rate_measurement.value
    dev.heart_rate_service.heart_rate_measurement.notifying=False

    try:
        dev.heart_rate_service.heart_rate_control_point.reset_expended()
    except KeyError: # no such characteristic, it's optional
        pass

finally:
    ble.done()
