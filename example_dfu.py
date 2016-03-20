#!/usr/bin/python

import os

zipfilename = os.path.expanduser('~/firmware.zip')
device_name = os.getenv('BLE_DEVICE_NAME') or 'Example Device'

import ble

try:
    dev = ble.discover_device(lambda d: d['Name'] == device_name)

    #address='cd:83:22:a3:1c:5e'
    #dev=ble.Device(address)
    dev.connect()
    address = dev.address

    #print "battery level",dev.battery_service.battery_level.read()

    #print "DFU version",dev.dfu_service.dfu_version.read()
    
    dev.dfu_service.quick_start_dfu(0)
    dev.disconnect()
    
    import time
    time.sleep(1)
    
    dev=ble.Device(address)
    dev.connect()

    try:
        dev.dfu_service.load_zip_file(zipfilename)

    except:
        print "Resetting"
        dev.dfu_service.reset_dfu()
        raise

finally:
    ble.done()
