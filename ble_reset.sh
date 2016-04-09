#!/usr/bin/env bash
# This script may get the local bluetooth device out of a funk.

sudo service bluetooth stop
sudo rm -r /var/lib/bluetooth
sudo service bluetooth start