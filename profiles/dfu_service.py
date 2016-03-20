#!/usr/bin/python2

import ble
import uuids

nordic_base='-1212-efde-1523-785feabcd123'

# The Nordic device-firmware-update protocol is described in 
# http://infocenter.nordicsemi.com/topic/com.nordic.infocenter.sdk51.v10.0.0/group__dfu__bootloader__api.html?cp=4_0_1_6_5
# http://infocenter.nordicsemi.com/topic/com.nordic.infocenter.sdk51.v10.0.0/examples_bootloader.html?cp=4_0_1_4_3

# role requirements:
# http://infocenter.nordicsemi.com/topic/com.nordic.infocenter.sdk51.v10.0.0/bledfu_transport_bleprofile.html?cp=4_0_1_4_3_1_4_0_1#ota_profile_updater_role_req

START_DFU=1
INITIALIZE_DFU_PARAMETERS=2
RECEIVE_FW_PARAMETERS=3
VALIDATE_FW=4
ACTIVATE_IMAGE=5
RESET_SYSTEM=6
REPORT_RECEIVED_IMAGE_SIZE=7
PACKET_RECEIPT_NOTIFICATION_REQUEST=8
RESPONSE_CODE=16
RECEIPT_NOTIFICATION=17

SUCCESS=1
INVALID_STATE=2
class InvalidState(Exception): pass
NOT_SUPPORTED=3
class NotSupported(Exception): pass
DATA_SIZE_EXCEEDS_LIMIT=4
class DataSizeExceedsLimit(Exception): pass
CRC_ERROR=5
class CRCError(Exception): pass
OPERATION_FAILED=6
class OperationFailed(Exception): pass

NO_IMAGE=0
SOFTDEVICE_IMAGE=1
BOOTLOADER_IMAGE=2
APPLICATION_IMAGE=4

class DfuService(ble.Service):
    uuid_def=('00001530'+nordic_base,'dfu_service','Nordic DFU Service')

    def load_zip_file(self, filename):
        import zipfile
        import json

        zf=zipfile.ZipFile(filename)

        manifest=json.load(zf.open('manifest.json'))['manifest']['application']

        dat_file = zf.open(manifest['dat_file']).read()
        bin_file = zf.open(manifest['bin_file']).read()

        self.start_dfu_application(len(bin_file))
        self.send_init(dat_file)
        self.send_image(bin_file)
        self.validate_image()
        self.activate_image()

        print "done."

    def quick_start_dfu(self, image_type):
        self.dfu_control_point.notifying=True
        try:
            self.dfu_control_point.value = [START_DFU,image_type]
        except ble.BleException:
            pass

    def check_response_value(self, response_value):
        if response_value==SUCCESS: return True
        elif response_value==INVALID_STATE: raise InvalidState
        elif response_value==NOT_SUPPORTED: raise NotSupported
        elif response_value==DATA_SIZE_EXCEEDS_LIMIT: raise DataSizeExceedsLimit
        elif response_value==CRC_ERROR: raise CRCError
        elif response_value==OPERATION_FAILED: raise OperationFailed
        else: raise Exception("unknown response")

    def start_dfu_none(self):
        self._start_dfu(NO_IMAGE,(0,0,0))
    def start_dfu_softdevice(self,length):
        self._start_dfu(SOFTDEVICE_IMAGE,(length,0,0))
    def start_dfu_bootloader(self,length):
        self._start_dfu(BOOTLOADER_IMAGE,(0,length,0))
    def start_dfu_application(self,length):
        self._start_dfu(APPLICATION_IMAGE,(0,0,length))

    def _start_dfu(self, image_type, lengths):
        cp = self.dfu_control_point
        pk = self.dfu_packet

        if cp.notifying:
            # workaround from https://github.com/thegecko/web-bluetooth-dfu
            cp.notifying=False

        cp.notifying=True
        cp.value=[START_DFU,image_type]
        
        print "started"
        pk.write_image_size(lengths)

        resp = cp.value

        assert(resp[0]==RESPONSE_CODE)
        assert(resp[1]==START_DFU)
        self.check_response_value(resp[2])
    
    def send_init(self, contents):
        RECEIVE_INIT_PACKET=0
        INIT_PACKET_COMPLETE=1

        cp = self.dfu_control_point
        pk = self.dfu_packet

        cp.notifying=True
        cp.value = [INITIALIZE_DFU_PARAMETERS,
                    RECEIVE_INIT_PACKET]

        print "initted"
        pk.write_init_packet(contents)

        cp.value = [INITIALIZE_DFU_PARAMETERS,
                    INIT_PACKET_COMPLETE]

        resp = cp.value

        assert(resp[0]==RESPONSE_CODE)
        assert(resp[1]==INITIALIZE_DFU_PARAMETERS)
        self.check_response_value(resp[2])

    def send_image(self, contents):
        cp = self.dfu_control_point
        pk = self.dfu_packet

        cp.notifying=True
        cp.value = [RECEIVE_FW_PARAMETERS]

        print "sending fw"
        pk.write_fw_image(contents)

        resp = cp.value

        assert(resp[0]==RESPONSE_CODE)
        assert(resp[1]==RECEIVE_FW_PARAMETERS)
        self.check_response_value(resp[2])

    def validate_image(self):
        cp = self.dfu_control_point

        cp.notifying=True
        cp.value = [VALIDATE_FW]

        print "validating fw"

        resp = cp.value
        assert(resp[0]==RESPONSE_CODE)
        assert(resp[1]==VALIDATE_FW)
        self.check_response_value(resp[2])

    def activate_image(self):
        cp = self.dfu_control_point
        try:
            cp.write([ACTIVATE_IMAGE],True)
        except ble.BleException: # already reset, didn't ack
            pass

    def reset_dfu(self):
        cp = self.dfu_control_point
        try:
            self.value = [RESET_SYSTEM]
        except: # ble.BleException: # already reset, didn't ack
            pass

class DfuPacket(ble.Characteristic):
    uuid_def=('00001532'+nordic_base,'dfu_packet','Nordic DFU Packet')

    def write_image_size(self, sizes):
        val=[]
        for size in sizes:
            val += [size>>0 & 0xff,
                    size>>8 & 0xff,
                    size>>16 & 0xff,
                    size>>24 & 0xff]
        self.value = val

    def _chunked_write(self, data):
        while data:
            self.raw = data[:20]
            data = data[20:]

    def write_init_packet(self, packet):        
        self._chunked_write(packet)

    def write_fw_image(self, packet):        
        self._chunked_write(packet)

class DfuStatus(ble.Characteristic):
    uuid_def=('00001533'+nordic_base,'dfu_status','Nordic DFU Status')

class DfuControlPoint(ble.Characteristic):
    uuid_def=('00001531'+nordic_base,'dfu_control_point','Nordic DFU Control Point')

class DfuVersion(ble.Characteristic):
    uuid_def=('00001534'+nordic_base,'dfu_version','Nordic DFU Version')

if __name__=="__main__":
    print "hi"
