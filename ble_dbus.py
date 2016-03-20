#!/usr/bin/python2

# http://cheesehead-techblog.blogspot.com/2012/11/dbus-tutorial-gobject-introspection.html

import uuids
import uuid_registry

import dbus
import dbus.service
try:
    from gi.repository import GObject
except ImportError:
    import gobject as GObject

from dbus.mainloop.glib import DBusGMainLoop,threads_init

threads_init()
DBusGMainLoop(set_as_default=True)

import threading,Queue

mainloop = GObject.MainLoop()

ble_thread = threading.Thread(target=mainloop.run)
ble_thread.start()

system_bus = dbus.SystemBus()

manager = dbus.Interface(system_bus.get_object("org.bluez", "/"),
                         "org.freedesktop.DBus.ObjectManager")


hci0 = system_bus.get_object("org.bluez",
                             '/org/bluez/hci0')
adapter = dbus.Interface(hci0,
                         'org.bluez.Adapter1')
props = dbus.Interface(hci0,
                       'org.freedesktop.DBus.Properties')

def printf(*args, **kwargs):
    print args 
    print kwargs

#system_bus.add_signal_receiver(printf,'org')

def introspect_devices():
    d = dbus.Interface(hci0,"org.freedesktop.DBus.Introspectable").Introspect()
    import xml.etree.ElementTree as ET

    root = ET.fromstring(d)
    names = [child.attrib['name'] 
             for child in root.findall('node') 
             if child.attrib['name'].startswith('dev_')]

    return names

def introspect_child_nodes(path):
    obj = system_bus.get_object("org.bluez", path)
    d = dbus.Interface(obj,"org.freedesktop.DBus.Introspectable").Introspect()
    import xml.etree.ElementTree as ET

    root = ET.fromstring(d)
    return [child.attrib['name'] 
            for child in root.findall('node')]
    
def filtered_child_names(path, filter_function):
    child_names = filter(filter_function, introspect_child_nodes(path))

    return ['/'.join((path, name)) for name in child_names]

def introspect_services(device_path):
    return filtered_child_names(device_path,
                                lambda n: n.startswith('service'))

def introspect_characteristics(service_path):
    return filtered_child_names(service_path,
                                lambda n: n.startswith('char'))

class NotSupportedException(Exception): pass
class NoNotifyException(Exception): pass
class BleException(Exception): pass

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

    def __init__(self,char_name): 
        """char_name is a path in dbus, eg /org/bluez/hci0/dev_CB.../service0012/char0013"""
        self.path=char_name
        self.devnode = system_bus.get_object("org.bluez", self.path)
        self.props = dbus.Interface(self.devnode,"org.freedesktop.DBus.Properties")
        self.methods = dbus.Interface(self.devnode,"org.bluez.GattCharacteristic1")
        self.uuid = str(self['UUID'])

        try:
            self.__class__ = uuid_registry.lookup_uuid(self.uuid)
        except KeyError:
            pass

        self._notify_timeout=15.0
        self.notify_counter=0
        self.notify_queue=Queue.Queue()
        self.value_lock=threading.Lock()

        # Start with read/write disabled, choose default per properties
        self._write_procedure=DISALLOWED
        self._read_procedure=DISALLOWED

        if self.readable:
            self._read_procedure=REQUEST

        if self.writeable:
            self._write_procedure=COMMAND
        elif self.write_requestable:
            self._write_procedure=REQUEST
            
        self.notify_event=threading.Event()

    def __getitem__(self, item):
        return self.props.Get('org.bluez.GattCharacteristic1',item)

    def __repr__(self):
        return uuids.uuid_printable(self.uuid)
        return "Characteristic('%s')"%self.path

    @property
    def flags(self):
        return [str(f) 
                for f in self['Flags']]

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
        return dbus.Interface(self.devnode,"org.bluez.GattCharacteristic1").ReadValue()
    
    def write(self, value, ignoreme=False):
        try:
            dbus.Interface(self.devnode,"org.bluez.GattCharacteristic1").WriteValue(value)
        except:
            raise BleException

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
            return self.read()
        elif self._read_procedure in (NOTIFY,INDICATE):
            return self.notify_queue.get(timeout=self._notify_timeout)
        else:
            raise IOError("Read not allowed or notifications not set")

    @raw.setter
    def raw(self,val):
        # no API way to distinguish write command and write request
        # that I can discern.
        if self._write_procedure in (COMMAND, REQUEST):
            return self.write([ord(c) for c in val])
        else:
            raise IOError("Write not allowed")

    @property
    def value(self):
        if 'String' in repr(self) or 'Name' in repr(self):
            return self.raw.rstrip('\0')
        else:
            return [ord(str(c)) for c in self.raw]

    @value.setter
    def value(self, val):
        if 'String' in repr(self) or 'Name' in repr(self):
            self.raw=str(val)+'\0'
        else:
            self.raw=''.join(chr(c) for c in val)

    def _notify_reply_cb(self):
        pass
        
    def _notify_cb(self, iface, changed_props, invalidated_props):

        if iface != 'org.bluez.GattCharacteristic1':
            return

        if not len(changed_props):
            return

        value = changed_props.get('Value', None)
        if not value:
            return

        # Remove the useless d-bus wrapper
        value = ''.join(chr(d) for d in value)

        with self.value_lock:
            self.notify_queue.put(value)
            self._last_raw = value
            self.notify_counter+=1
        
    def _error_cb(self, value):
        raise Exception(value)

    @property
    def last_raw(self):
        with self.value_lock:
            ret=self._last_raw
        return ret

    @property
    def notifying(self):
        return bool(self['Notifying'])

    @notifying.setter
    def notifying(self, value):
        if not self.notifyable and not self.indicatable:
            raise Exception("not notifyable")
        if value and self.notifying:
            # already notifying
            return

        if not value and not self.notifying:
            # already not notifying
            return
            
        if value:
            self._val=None
            self.props.connect_to_signal("PropertiesChanged",
                                         self._notify_cb)

            self.notify_event.clear()
            self.methods.StartNotify(
                reply_handler = self._notify_reply_cb,
                error_handler = self._error_cb,
            )
            self._read_procedure = NOTIFY
        else:
            self.methods.StopNotify()

    def notify(self, notify_func):
        self.methods.StartNotify()

    def notifyx(self, notify_func):
        self.methods.StartNotify(reply_handler=notify_func,
                                 error_handler=printf,
                                 dbus_interface="org.bluez.GattCharacteristic1")

class Service(uuid_registry.UUIDClass):
    def __init__(self,service_name): 
        """service_name is a path in dbus, eg /org/bluez/hci0/dev_CB.../service0012"""
        self.path=service_name
        devnode = system_bus.get_object("org.bluez", self.path)
        self.props = dbus.Interface(devnode,"org.freedesktop.DBus.Properties")
        uuid = self.props.Get('org.bluez.GattService1','UUID')
        self.uuid = str(uuid)
        self._chars = None # lazy-load characteristics to avoid
                           # unnessary discovery.

        try:
            self.__class__ = uuid_registry.lookup_uuid(self.uuid)
        except KeyError:
            pass

    def __getattr__(self,item):
        if self._chars is None:
            self.characteristics
        #if item in dir(self):
        return self.__dict__[item]
        #else:
        #    raise AttributeError
        
    @property
    def characteristics(self):
        if self._chars == None:
            self._chars = []
            #for char in self.props.Get('org.bluez.GattService1','Characteristics'):
            for char in introspect_characteristics(self.path):
                c = Characteristic(char)
                name = uuids.uuid_identifier(c.uuid)
                setattr(self,name,c)
                self._chars.append(c)

        return self._chars

    def __repr__(self):        
        return uuids.uuid_printable(self.uuid)
        return "Service('%s')"%self.path

class Device(uuid_registry.UUIDClass):
    def __init__(self,device_name):
        """where device_name starts with 'dev_'"""
        if ":" in device_name:
            # we've got an address
            device_name="_".join(["dev"]+device_name.split(":"))
        
        self.path="/org/bluez/hci0/%s"%device_name

        self.devnode = system_bus.get_object("org.bluez", self.path)

        uuids = self['UUIDs']
        self.iface = dbus.Interface(self.devnode, "org.bluez.Device1")
        self.uuids = [str(uuid) for uuid in uuids]
        self.address = self['Address']

    def _services(self):
        ret=[]
        t0=time.time()
        timed_out=False
        if 0:
        # GattServices property does not show until discovery finishes
            while not timed_out:
                try:
                    #service_list = self['GattServices']
                    break
                except:
                    timed_out = time.time() > (t0+10)

            if timed_out:
                raise
                
        else:
            while not timed_out:
                try:
                    if self['ServicesResolved']:
                        break
                except:
                    timed_out = time.time() > (t0+100)

            if timed_out:
                raise

        for service in introspect_services(self.path):
            s = Service(service)
            name = uuids.uuid_identifier(s.uuid)
            #print "name",name,"=",s
            if not name.endswith('_service'):
                name+='_service'
            setattr(self,name,s)
            ret.append(s)
        return ret
    
    @property
    def props(self):
        return dbus.Interface(self.devnode,"org.freedesktop.DBus.Properties")

    def __getitem__(self, item):
        return self.props.Get('org.bluez.Device1',item)

    def connect(self):
        self.iface.Connect()
        while not self.connected():
            print "waiting"
            pass
        self.services=self._services()

        return self
    
    def connected(self):
        return self['Connected']
        while self.connected():
            print "waiting"

    def disconnect(self):
        self.iface.Disconnect()

        
    def __repr__(self):
        return "Device('%s')"%self.path

    def __enter__(self):
        return self
        
    def __exit__(self,exception_type,exception_value,traceback):
        self.iface.Disconnect()
        #print exception_type,exception_value,traceback
        return False


def power(onoff=True, block=True):
    if onoff==props.Get('org.bluez.Adapter1','Powered'):
        return

    props.Set('org.bluez.Adapter1','Powered', onoff)

    if block:
        while onoff!=props.Get('org.bluez.Adapter1','Powered'):
            print "waiting",
    

def discover(onoff=True, block=True):
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

def discover_devices(scanfunc=None, uuid=None, timeout=6, limitone=False):

    if scanfunc is None: scanfunc=lambda d:True

    power()
    discover()
    t0=time.time()
    ret=set()
    devnames = set()

    while timeout is None or time.time() < t0+timeout:
        for devname in introspect_devices():
            if not devname in devnames:
                devnames.add(devname)
                device = Device(devname)
                if uuid is None or uuid in device.uuids:
                    if scanfunc(device):
                        yield device
                        if limitone:
                            break

def discover_device(scanfunc=None, uuid=None, timeout=6):
    for d in discover_devices(scanfunc, uuid, timeout, limitone=True):
        return d

def done():
    mainloop.quit()
    ble_thread.join()

if __name__=="__main__":
    #for d in discover_devices():
    #    print d.uuids
    print discover_device(lambda d:d['Name'].startswith('Pico'))

