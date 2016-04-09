#!/usr/bin/python2

"""Setup a metaclass that automatically registers the uuid->class mapping
in a dictionary.
"""

import os,sys,uuids
thispath = os.path.dirname(os.path.realpath(__file__))

def load_classes(directory=None):
    from os.path import join,isfile,basename

    directory=directory or join(thispath,'profiles')

    import glob
    modules = glob.glob(directory+"/*.py")
    sys.path = [directory] + sys.path
    profiles = map(__import__,[basename(f)[:-3] for f in modules if isfile(f)])
    sys.path.pop(0)

uuid_registry={}

class UUIDMeta(type):
    def __new__(cls, name, parents, dct): 
        c = super(UUIDMeta, cls).__new__(cls, name, parents, dct)
        # print cls,name
        try:
            uuids.setup_uuid_type(*c.uuid_def)
            c.uuid=c.uuid_def[0]
        except AttributeError:
            pass            

        try:
            if c.uuid:
                uuid_registry[c.uuid]=c
        except AttributeError:
            pass
        return c

dict = uuid_registry

from six import add_metaclass
@add_metaclass(UUIDMeta)
class UUIDClass(object):
    uuid=None

def lookup_uuid(uuid):
    """Returns a class if there is a special one defined for this uuid.
    raises KeyError otherwise"""
    return uuid_registry[uuid]

