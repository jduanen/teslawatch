#!/usr/bin/env python

################################################################################
#
# Script to watch for Tesla state changes
#
# This is to run in the cloud and there will be an Android front-end to
#  manage the fences and this will issue notifications to the mobile device.
#
################################################################################

import argparse
import json
import os
import sys
import teslajson
import yaml

#### TODO:
####  * Geofence -- notify when arriving/departing locations (e.g., home)
####  * notify on state transitions (was moving and now stopped, vice versa)
####  * monitor temp and turn on a/c if too hot
####  * look at weather and make sure roof is closed if raining
####  * update more frequently when moving
####  * notify if within X distance of current location
####  * rewrite all of this
####  * use multiple instances or multiprocessing to handle multiple cars
####  * focus on state transitions: states=[parked, moving], events=[parked->moving, moving->parked]
####  * different polling intervals for different states -- e.g., parked@home, nighttime, moving, etc.
####  * use different packages to send SMS notifications
####    - textbelt
####    - google hangouts: "hangups" package pythone3
####  * make notification backend be pluggable
####  * rewrite to be Python3
####  * fix up the cmd-line interface
####  * build mapping front-end to define/display geofences
####  * make basic features work without geofencing
####  * define config file format

#### FIXME keep textbelt key secret too

'''
DESIGN NOTES:
* Array of cars objects
* Region Object encapsulates
  - coordinates that define a closed region
    * e.g., center and radius, polygon vertices
* Car Object encapsulates
  - state of car
    * States: Parked (Home/Work/Other), Moving, Stopped, Unknown
    * recent history of states
  - secrets/keys associated with car
  - event handler callback
  - Region objects
    * defined Home and Work regions
    * other regions of interest for the car
* Config file:
  - YAML
  - secret/protected file
  - read/updated by app
  - one or more cars
  - contents
    * user name
    * VIN
    * Tesla API id/secret
    * Regions (Home/Work/other)
    * messaging info
      - SMS: phone number, API key
  - process:
    * read from file
    * match up VIN numbers with those returned from Tesla API
    * instantiate car object for each match
    * (optionally) whine about mismatches (on either side)

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

DEF_CONFIGS_PATH = "./.teslas.yml"


#### TODO move this to 'tesla.py'
# Car object that encapsulates the state of a car,
class Car(object):
    def __init__(self, vin, config, vehicle):
        self.vin = vin
        self.config = config
        self.vehicle = vehicle

    def dump(self):
        pass


#
# MAIN
#
def main():
    # Print the given message, print the usage string, and exit with an error.
    def fatalError(msg):
        sys.stderr.write("Error: {0}\n".format(msg))
        sys.stderr.write("Usage: {0}\n".format(usage))
        sys.exit(1)

    usage = "Usage: {0} [-v] [-c <configsFile>] [-V <VIN>]"
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-c", "--configsFile", action="store", type=str,
        default=DEF_CONFIGS_PATH, help="path to file with configurations")
    ap.add_argument(
        "-p", "--password", action="store", type=str, help="user password")
    ap.add_argument(
        "-v", "--verbose", action="count", default=0, help="print debug info")
    ap.add_argument(
        "-V", "--VIN", action="store", type=str,
        help="VIN of car to use (defaults to all found in config file")
    options = ap.parse_args()

    if not os.path.exists(options.configsFile):
        fatalError("Invalid configuration file: {0}".format(options.configsFile))

    #### TODO add check if configs file has proper protections

    with open(options.configsFile, "r") as confsFile:
        confs = list(yaml.load_all(confsFile))[0]
    json.dump(confs, sys.stdout, indent=4, sort_keys=True)    #### TMP TMP TMP
    print("")

    if options.VIN:
        carVINs = [options.VIN]
    else:
        carVINs = confs['CARS'].keys()
    if options.verbose:
        print("CARS: {0}".format(carVINs))

    user = confs.get('USER')
    if not user:
        user = raw_input("user: ")
    if options.verbose:
        print("USER: {0}".format(user))

    if options.password:
        password = options.password
    else:
        password = confs.get('PASSWD')
    if not password:
        password = raw_input("password: ")
    if options.verbose:
        print("PASSWD: {0}".format(password))

    try:
        conn = teslajson.Connection(user, password)
    except Exception as e:
        fatalError("Failed to connect {0}".format(e))
    if options.verbose > 1:
        print("CONNECTION: {0}".format(conn))
        print("")

    if options.verbose > 1:
        print "Number of vehicles: {0}".format(len(conn.vehicles))
        n = 1
        for v in conn.vehicles:
            print "Vehicle #{0}:".format(n)
            json.dump(v, sys.stdout, indent=4, sort_keys=True)
            print("")
            n += 1

    teslaVINs = [v['vin'] for v in conn.vehicles]
    vinList = [v for v in teslaVINs if v in carVINs]
    if not vinList:
        fatalError("Unable to find requested cars in Tesla API")

    notFound = list(set(carVINs) - set(vinList))
    if notFound:
        fatalError("Cars asked for, but not found in Tesla API: {0}".format(notFound))

    if options.verbose:
        print("Watching: {0}".format(vinList))
        notAskedFor = list(set(teslaVINs) - set(vinList))
        if notAskedFor:
            print("Cars Tesla API knows about, but not asked for: {0}".format(notAskedFor))

    vehicles = {v['vin']: v for v in conn.vehicles if v['vin'] in vinList}
    if options.verbose > 1:
        print("VEHICLES:")
        json.dump(vehicles, sys.stdout, indent=4, sort_keys=True)
        print("")

    cars = {}
    for vin in vinList:
        cars[vin] = Car(vin, confs['CARS'][vin], vehicles[vin])

    #### TODO wake up all the cars in 'vinList'
    for v, c in cars.items():
        ????

    #### TODO wait a bit and then go get initial data from each of the cars

    #### TODO launch tracker threads for each car


if __name__ == '__main__':
    main()
