#!/usr/bin/python2

import os,sys

thispath = os.path.dirname(os.path.realpath(__file__))
uuid_dict={}

def setup_uuid_type(uuid, ident_name, desc_name):        

    uuid_dict[uuid]=ident_name,desc_name

    if globals().has_key(ident_name):
        # oops, name collision. add uuid suffix
        old_uuid=globals()[ident_name]
        short_id=int(old_uuid.split('-')[0],16)            
        globals()[ident_name+"_0x%x"%short_id]=old_uuid
        del globals()[ident_name]

        short_id=int(uuid.split('-')[0],16)            
        globals()[ident_name+"_0x%x"%short_id]=uuid
    else:
        globals()[ident_name]=uuid

def canonical_uuid(uuid):
    if type(uuid)==int:
        uuid=str(uuid)

    if len(uuid) < 32:
        uuid="%08x-0000-1000-8000-00805f9b34fb"%int(uuid,0)

    return uuid

def _setup_uuid_types(uuids_list,suffix=''):
    for uuid,name1,name2 in uuids_list:
        uuid = canonical_uuid(uuid)
        
        name1=name1.encode('ascii','replace')
        name1=name1.replace('-','_').replace('?','_')

        setup_uuid_type(uuid, name1, name2+suffix)

def uuid_pair(uuid):
    uuid=str(uuid)
    return uuid_dict[uuid]
   
def uuid_identifier(uuid):
    return uuid_pair(uuid)[0]

def uuid_printable(uuid):
    return uuid_pair(uuid)[1]

def _setup_json():
    import json
    uuids = json.load(file(os.path.join(thispath,'uuids.json')))

    _setup_uuid_types(uuids['service_UUIDs'],' Service')
    _setup_uuid_types(uuids['characteristic_UUIDs'],' Characteristic')
    _setup_uuid_types(uuids['descriptor_UUIDs'],' Descriptor')
    _setup_uuid_types(uuids['units_UUIDs'],' Units')

_setup_json()

if __name__=="__main__":
    print dir()

    

