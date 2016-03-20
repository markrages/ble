#!/usr/bin/python

import ble
import os

device_name = os.getenv('BLE_DEVICE_NAME') or 'Example Device'

try:
    dev = ble.discover_device(lambda d: d['Name'] == device_name)
    dev.connect()

    print "battery level",dev.battery_service.battery_level.value

    dev.cycling_power_service.cycling_power_measurement.notifying=True
    print dev.cycling_power_service.cycling_power_measurement.value
    dev.cycling_power_service.cycling_power_measurement.notifying=False

    print dev.cycling_power_service.calibrate()

finally:
    ble.done()
