#!/usr/bin/env bash
#
#  Test Notifier Script -- just echos arg on console
#

if [ "$#" -ne 1 ]; then
    echo "ERROR: invalid number of args"
    exit 1
fi

echo ${0}: ${1}
