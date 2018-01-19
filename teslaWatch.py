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
