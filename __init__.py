#!/usr/bin/python

import sys,os
thispath = os.path.dirname(os.path.realpath(__file__))
sys.path.append(thispath)

import ble
from ble import *

uuid_registry.load_classes()
