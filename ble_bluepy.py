#!/usr/bin/python2

import uuids
import uuid_registry

from bluepy import btle

import threading,Queue

class NotSupportedException(Exception): pass
class NoNotifyException(Exception): pass

COMMAND='command'
REQUEST='request'
NOTIFY='notify'
INDICATE='indicate'
DISALLOWED='disallowed'

notify_lock=threading.Lock()

class Characteristic(uuid_registry.UUIDClass):   
    """Represents GATT characteristic.

    properties:
    
      - value: the classes value, as decoded by the profile, or a list
        of uint8 values otherwise.

      - raw: the raw values in/out, as bytestring.

      - write_type. Set to ble.COMMAND or ble.REQUEST' as desired.

      - read_type. Set to ble.COMMAND, ble.REQUEST, ble.NOTIFY, ble.INDICATE

    """

    def __init__(self, btle_char): 
        self.char = btle_char
        self.uuid = str(self.char.uuid)

        flags = []

        # Start with read/write disabled, choose default per props flags
        self._write_procedure=DISALLOWED
        self._read_procedure=DISALLOWED

        props = btle.Characteristic.props
        if self.char.properties & props['READ']:
            flags.append('read')
            self._read_procedure=REQUEST
        if self.char.properties & props['INDICATE']:
            flags.append('indicate')
        if self.char.properties & props['NOTIFY']:
            flags.append('notify')

        if self.char.properties & props['WRITE_NO_RESP']:
            self._write_procedure=COMMAND
            flags.append('write_no_resp')
        if self.char.properties & props['WRITE']:
            self._write_procedure=REQUEST
            flags.append('write')
            
        self.flags=flags

        self._notify_timeout=15.0
        self.notify_counter=0
        self.notify_queue=Queue.Queue()
        self.value_lock=threading.Lock()

        self.descriptors=[]

    def add_descriptors(self, descriptors):
        self.descriptors+=descriptors
        for d in descriptors:
            if str(d.uuid)==uuids.client_characteristic_configuration:
                self.cccd = d

    def write_cccd(self, val):
        self.cccd.peripheral.writeCharacteristic(self.cccd.handle, val, True)

    def read_cccd(self):
        return self.cccd.peripheral.readCharacteristic(self.cccd.handle)
            
    def __repr__(self):
        return uuids.uuid_printable(self.uuid)

    @property
    def readable(self):
        return 'read' in self.flags

    @property
    def notifyable(self):
        return 'notify' in self.flags

    @property
    def indicatable(self):
        return 'indicate' in self.flags

    @property
    def writeable(self):
        return 'write_no_resp' in self.flags

    @property
    def write_requestable(self):
        return 'write' in self.flags

    def read(self):
        new_val = [ord(c) for c in self.char.read()]
        self._val = new_val       
        return self.value
    
    def write(self, value, response=None):
        if response is None:
            response=self._write_resp
        val = ''.join(chr(c) for c in value)
        self.char.write(val, response)

    @property
    def notify_timeout(self):
        return self._notify_timeout
        
    @notify_timeout.setter
    def notify_timeout(self,value):
        self._notify_timeout=float(self._notify_timeout)

    @property
    def read_procedure(self):
        return self._read_procedure
    @read_procedure.setter
    def read_procedure(self,proc):
        if proc==REQUEST:
            if not self.readable:
                raise ValueError("read request not allowed")
        elif proc==COMMAND:
            if not self.readable:
                raise ValueError("read command not allowed")
        elif proc==NOTIFY:
            if not self.notifyable:
                raise ValueError("notify not allowed")
            self.notifying=True
        elif proc==INDICATE:
            if not self.indicatable:
                raise ValueError("indicate not allowed")
            self.notifying=True
        else:
            raise ValueError("unknown read procedure")
        self._read_procedure=proc

    @property
    def write_procedure(self):
        return self._write_procedure
    @write_procedure.setter
    def write_procedure(self,proc):
        if proc==REQUEST:
            if not self.writeable:
                raise ValueError("write request not allowed")
        elif proc==COMMAND:
            if not not self.writeable:
                raise ValueError("write command not allowed")
        else:
            raise ValueError("unknown write procedure")

        self._write_procedure=proc
                
    @property
    def raw(self):
        if self._read_procedure in (REQUEST,COMMAND):
            return self.char.read()
        elif self._read_procedure in (NOTIFY,INDICATE):
            try:
                return self.notify_queue.get(block=False)
            except Queue.Empty:
                self._wait_notify(self._notify_timeout)
                return self.notify_queue.get(block=False)
        else:
            raise IOError("Read not allowed or notifications not set")

    @raw.setter
    def raw(self,val):
        if self._write_procedure==COMMAND:
            return self.char.write(val, False)
        elif self._write_procedure==REQUEST:
            return self.char.write(val, True)
        else:
            raise IOError("Write not allowed")

    @property
    def value(self):
        if 'String' in repr(self) or 'Name' in repr(self):
            return self.raw.rstrip('\0')
        else:
            return [ord(c) for c in self.raw]

    @value.setter
    def value(self, val):
        if 'String' in repr(self) or 'Name' in repr(self):
            self.raw=str(val)+'\0'
        else:
            self.raw=''.join(chr(c) for c in val)

    def _notify_reply_cb(self):
        pass
        
    def _notify_cb(self, data):
        with self.value_lock:
            self.notify_queue.put(data)
            self._last_raw = data
            self.notify_counter+=1
            
    @property
    def last_raw(self):
        with self.value_lock:
            ret=self._last_raw
        return ret

    def _error_cb(self, value):
        raise Exception(value)

    @property
    def notifying(self):
        return self.read_cccd() != '\0\0'

    @notifying.setter
    def notifying(self, value):        
        if not self.notifyable and not self.indicatable:
            raise Exception("not notifyable")
        if value:
            handle=self.char.handle+1
            with notify_lock:
                self.char.peripheral.delegate.notification_callbacks[handle]=self._notify_cb

            if self.indicatable:
                self.write_cccd('\2\0')
                self._read_procedure = INDICATE
            else:
                self.write_cccd('\1\0')
                self._read_procedure = NOTIFY

        else:
            self.write_cccd('\0\0')

    def _wait_notify(self, timeout):

        timeout_time=time.time()+timeout
        with self.value_lock:
            initial_counter = self.notify_counter

        while 1:
            retval=self.char.peripheral._getResp(['ntfy','ind'], timeout_time-time.time())
            
            with self.value_lock:
                now_counter = self.notify_counter

            if initial_counter != now_counter: 
                break

            if retval is None:
                raise NoNotifyException

class Service(uuid_registry.UUIDClass):
    def __init__(self, btle_service): 
        self.serv = btle_service

        self.uuid = str(btle_service.uuid)
        self._chars = None # lazy-load characteristics to avoid
                           # unnessary discovery.

    def __getattr__(self,att):
        self.characteristics
        return self.__dict__[att]

    def _get_characteristics(self):
        ret = []
        chars = list(self.serv.getCharacteristics())
        handle_pairs=[]
        char_handles=[c.getHandle() for c in chars]+[self.serv.hndEnd+1]
        handle_pairs = zip(char_handles[:-1],char_handles[1:])

        for char,(start,end) in zip(chars,handle_pairs):
            uuid = str(char.uuid)

            cls=None
            try:
                cls = uuid_registry.lookup_uuid(uuid)
            except KeyError:
                cls = Characteristic
            c=cls(char)

            for handle in range(start+1,end):
                try:
                    more_descriptors = char.peripheral.getDescriptors(handle,handle)
                except btle.BTLEException:
                    if end < 65535:
                        raise
                    break

                c.add_descriptors(more_descriptors)
                
            name = uuids.uuid_identifier(c.uuid)
            setattr(self,name,c)
            ret.append(c)

        return ret

    @property
    def characteristics(self):
        if self._chars is None:
            self._chars = self._get_characteristics()
        return self._chars

    def __repr__(self):
        return uuids.uuid_printable(self.uuid)

class Device(uuid_registry.UUIDClass):
    def __init__(self, bluepy_device):

        if type(bluepy_device) in (str,unicode):
            self.address = bluepy_device
            self.atype = btle.ADDR_TYPE_RANDOM
            
        else:
            self.scanentry=bluepy_device

            self.scandata={}
            for _,name,val in self.scanentry.getScanData():
                self.scandata[name]=val
            self.scandata['Name']=str(self.scandata['Complete Local Name'])

            uuid_iter = iter(self.scandata['Complete 16b Services'])
            def uuid_16s():
                while 1:
                    lsb = int(uuid_iter.next()+uuid_iter.next(),16)
                    msb = int(uuid_iter.next()+uuid_iter.next(),16)
                    yield 256*msb+lsb

            self.uuids = [uuids.canonical_uuid(uuid) for uuid in uuid_16s()]

            self.address = self.scanentry.addr
            self.atype = self.scanentry.atype

    def _notify_cb(self, handle, data):
        with notify_lock:
            try:
                cb = self.dev.delegate.notification_callbacks[handle]
            except KeyError:
                print "got notification for unexpected callback %d"%handle
                cb = lambda x:None

        return cb(data)


    def _services(self): 
        self.dev.delegate.notification_callbacks={}
        self.dev.delegate.handleNotification=self._notify_cb

        ret = []

        for service in self.dev.getServices():

            try:
                cls = uuid_registry.lookup_uuid(str(service.uuid))
            except KeyError:
                cls = Service

            s = cls(service)

            name = uuids.uuid_identifier(s.uuid)
            #print "name",name,"=",s
            if not name.endswith('_service'):
                name+='_service'
            setattr(self,name,s)
            ret.append(s)
        return ret
    
    @property
    def props(self):
        raise Exception

    def __getitem__(self, item):
        return self.scandata[item]

    def connect(self):
        self.dev = btle.Peripheral(self.address,
                                   self.atype)
        self.services=self._services()
        return self

    def disconnect(self):
        self.dev.disconnect()
    
    def connected(self):
        return self['Connected']
        
    def __repr__(self):
        return "Device('%s')"%self.address

    def __enter__(self):
        return self
        
    def __exit__(self,exception_type,exception_value,traceback):
        self.iface.Disconnect()
        #print exception_type,exception_value,traceback
        return False


def power(onoff=True, block=True):
    return
    if onoff==props.Get('org.bluez.Adapter1','Powered'):
        return

    props.Set('org.bluez.Adapter1','Powered', onoff)

    if block:
        while onoff!=props.Get('org.bluez.Adapter1','Powered'):
            print "waiting",
    

def discover(onoff=True, block=True):
    return
    if onoff==props.Get('org.bluez.Adapter1','Discovering'):
        return

    if onoff:
        adapter.StartDiscovery()
    else:
        adapter.StopDiscovery()

    if block:
        while onoff!=props.Get('org.bluez.Adapter1','Discovering'):
            #print "waiting",
            pass

import time

class ScanPrint(btle.DefaultDelegate):
    def handleDiscovery(self, dev, isNewDev, isNewData):
        pass

def discover_devices(scanfunc=None, uuid=None, timeout=6, limitone=False):

    if scanfunc is None: scanfunc=lambda d:True

    scanner = btle.Scanner().withDelegate(ScanPrint())

    for d in scanner.scan(timeout):
        device=Device(d)

        if scanfunc(device):
            yield device

def discover_device(scanfunc=None, uuid=None, timeout=6):
    for d in discover_devices(scanfunc, uuid, timeout, limitone=True):
        return d
    raise IOError("Couldn't find device")

def done():
    pass

if __name__=="__main__":
    #for d in discover_devices():
    #    print d.uuids
    print discover_device(lambda d:d['Name'].startswith('Pico'))

