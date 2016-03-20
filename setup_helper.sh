#!/bin/sh
set -e

HELPER=$( /usr/bin/python -c 'import bluepy.btle; print bluepy.btle.helperExe' )


echo This script will setuid the $(basename $HELPER) binary on your system.
echo This is a security hole!

sudo chown root $HELPER
sudo chmod +s $HELPER

echo Done.
