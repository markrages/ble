#!/usr/bin/python

if 1:
    from ble_bluepy import *
else:
    from ble_dbus import *

try:    
    uuid_registry.load_classes()
except AttributeError:
    """We have mutually recursive module loading between ble_*.py and
    profiles/*.py.  This can cause errors when this module is imported
    indirectly, such as through __init__.py.  So ignore errors and
    trust that __init__.py will call load_classes() again.
    """
    pass
