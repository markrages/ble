#!/usr/bin/python2

import ble
import uuids

cateye_base='-ceed-1000-8000-00805f9b34fb'

class CateyeService(ble.Service):
    uuid_def=('00004001'+cateye_base,'cateye_service','Cateye Service')
