#!/usr/bin/python2

import ctypes
import os,sys,socket,errno

bt = ctypes.cdll.LoadLibrary('libbluetooth.so')

def errcheck(err, name):
    if err >= 0: return
    raise Exception("%s: Error %d"%(name,err))

uint8_t = ctypes.c_uint8
uint32_t = ctypes.c_uint32

class BdAddr(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("b", 6*uint8_t)]

class LeAdvertisingInfo(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("evt_type", uint8_t),
                ("bdaddr_type", uint8_t),
                ("bdaddr", BdAddr),
                ("length", uint8_t),
                ("data", ctypes.POINTER(uint8_t))]

class EvtLeMetaEvent(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("subevent", uint8_t),
                ("data", ctypes.POINTER(uint8_t))]

HCI_EVENT_PKT = 4
HCI_VENDOR_PKT = 0xff
EVT_LE_META_EVENT = 0x3E

class HciFilter(ctypes.Structure):
    _fields_ = [("type_mask", uint32_t),
                ("event_mask", 2*uint32_t),
                ("opcode", uint32_t)]
    def clear(self):
        ctypes.memset(ctypes.addressof(self), 0, ctypes.sizeof(self))

    def set_ptype(self, ptype):
        assert(ptype < 32)
        if ptype==HCI_VENDOR_PKT:
            self.type_mask |= (1<<0)
        else:
            self.type_mask |= (1<<(ptype & 31))

    def set_event(self, event):
        if event < 32:
            self.event_mask[0] |= (1<<event)
        else:
            self.event_mask[1] |= (1<<(event&31))

def ba2str(ba):
    return ':'.join("%02x"%ord(c) for c in reversed(tuple(ba)))

EIR_NAME_SHORT = 8
EIR_NAME_COMPLETE = 9

def eir_parse_name(advdata):
    while len(advdata):
        field_len = ord(advdata[0])
        field,advdata = advdata[1:1+field_len],advdata[1+field_len:]
        eir_type = ord(field[0])
        if eir_type in [EIR_NAME_SHORT, EIR_NAME_COMPLETE]:
            return field[1:]

def unpack(ctype_instance):
    return buffer(ctype_instance)[:]

def pack_into(ctype_instance, buf):
    fit = max(len(buf), ctypes.sizeof(ctype_instance))
    ctypes.memmove(ctypes.addressof(ctype_instance), buf, fit)
    return ctype_instance


bt.hci_open_dev.argtypes = [ctypes.c_int]
bt.hci_le_set_scan_parameters.argtypes = [ctypes.c_int,
                                          ctypes.c_uint8,
                                          ctypes.c_uint16,
                                          ctypes.c_uint16,
                                          ctypes.c_uint8,
                                          ctypes.c_uint8,
                                          ctypes.c_int]
bt.hci_le_set_scan_enable.argtype = [ctypes.c_int,
                                     ctypes.c_uint8,
                                     ctypes.c_uint8,
                                     ctypes.c_int]

def read_flags(data):
    # TODO:
    return 0

def check_report_filter(procedure, adv_info):

    # If no discovery procedure is set, all reports are treat as valid
    if procedure==0: return 1

    # Read flags AD type value from the advertising report if it
    # exists
    flags = read_flags(info.data[info.length])

    # TODO:
    return 0;

class Unimplemented(Exception): pass

import struct

EVT_LE_ADVERTISING_REPORT = 0x02


def unpack_r(fmt, data):
    size=struct.calcsize(fmt)
    datalen = ord(data[size])
    otherdata = data[size+1:size+1+datalen]    
    return struct.unpack(fmt,data[:size])+(otherdata,)

def decode_event(event): 
    "pass a string or something."
    if ord(event[0]) != HCI_EVENT_PKT:
        raise ValueError("Not an event.")

    evt,evt_data = unpack_r("<B",event[1:])
    ret={'evt':evt}   

    if evt==EVT_LE_META_EVENT:
        subevent,subevent_data = ord(evt_data[0]),evt_data[1:]
        ret['subevent']=subevent
        if subevent==EVT_LE_ADVERTISING_REPORT:
            (ret['evt_type'],
             ret['bdaddr_type'],
             bdaddr_buf,
             adv_data) = unpack_r("<BB6s",subevent_data[1:])

            ret['name']=eir_parse_name(adv_data)
            ret['bdaddr']=ba2str(bdaddr_buf)
        else:
            raise Unimplemented("subevent = %02x"%subevent)

    else:
        raise Unimplemented("event = %02x"%evt)

    return ret
        
def print_advertising_devices(dd, filter_type):

    HCI_MAX_EVENT_SIZE = 260

    nf = HciFilter()
    of = HciFilter()

    AF_BLUETOOTH=31
    BTPROTO_HCI=1
    SOL_HCI=0
    HCI_FILTER=2

    dds = socket.fromfd(dd, AF_BLUETOOTH, socket.SOCK_RAW, BTPROTO_HCI)

    sockopt = dds.getsockopt(SOL_HCI, HCI_FILTER, ctypes.sizeof(of))
    pack_into(of,sockopt)

    nf.clear()
    nf.set_ptype(HCI_EVENT_PKT)
    nf.set_event(EVT_LE_META_EVENT)

    # print " ".join("%x"%ord(b) for b in buffer(nf))

    dds.setsockopt(SOL_HCI, HCI_FILTER, nf)

    try:
        while 1:
            try:      
                buf = os.read(dd, HCI_MAX_EVENT_SIZE)
            except OSError as err:                
                if err.errno in (errno.EAGAIN,errno.EWOULDBLOCK):
                    continue
                raise
            
            event_data = decode_event(buf)
            # check_report_filter(filter_type, info):
            print "%(bdaddr)s %(name)s"%event_data

    finally:
        dds.setsockopt(SOL_HCI, HCI_FILTER, ctypes.pointer(of))
        print "wrapped up"

        dds.close()

    return 0


dev_id = bt.hci_get_route(None)
#print "dev_id",dev_id
errcheck(dev_id, "Get dev id")

dd = bt.hci_open_dev(dev_id)
#print "dd",dd
errcheck(dd,"open_dev")

scan_type = 0x01
interval = 0x0010
window = 0x0010
filter_type = 0
own_type = 1 # 1 for random
filter_dup = 1

err = bt.hci_le_set_scan_parameters(dd, scan_type, interval, window,
                                    own_type, 0x00, 1000)
errcheck(err, "set_scan_parameters")

try:
    err = bt.hci_le_set_scan_enable(dd, 0x01, filter_dup, 1000)
    errcheck(err, "set_scan_enable")

    err = print_advertising_devices(dd, filter_type)
    errcheck(err, "print_adv")

finally:
    err = bt.hci_le_set_scan_enable(dd, 0x00, filter_dup, 1000)
    errcheck(err, "set_scan_disable")
    
    err = bt.hci_close_dev(dd)
    errcheck(err, "close")

