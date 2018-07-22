#!/usr/bin/env python
'''
################################################################################
#
# Notification Handler Library for TeslaWatch Application
#
################################################################################
'''

import sys

'''
--------------------
import requests
requests.post('https://textbelt.com/text', {
  'phone': '5557727420',
  'message': 'Hello world',
  'key': 'textbelt',
})

$ curl -X POST https://textbelt.com/text \
       --data-urlencode phone='5557727420' \
       --data-urlencode message='Hello world' \
       -d key=textbelt
{"success":true,"textId":"2861516228856794","quotaRemaining":249}[jdn@jdnLinux teslawatch]$

$ curl https://textbelt.com/status/2861516228856794
{"success":true,"status":"DELIVERED"}
'''

'''
TODO:
  * look at how I did the JBOD drivers and make a subdir with Event Function
  * instantiate an EventHandler object that binds event types to Event Functions
  * create structure with Event types (and args)
'''

def main(args):
    if len(args) != 2:
        sys.stderr.write("Error: invalid number of args '{0}' != 2\n".format(len(args)))
        sys.exit(1)
    print("SMS: '{0}'".format(args[1]))


#
# MAIN
#
if __name__ == '__main__':
    main(sys.argv)
