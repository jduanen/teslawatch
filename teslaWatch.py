#!/usr/bin/env python

################################################################################
#
# Script to watch for Tesla state changes
#
# This is to run in the cloud and there will be an Android front-end to
#  manage the fences and this will issue notifications to the mobile device.
#
# N.B.
#  * Values given on command line override those in the config file.
#  * If no DB file is given (in either the config file or on the command line)
#    then nothing is logged to the DB.  Otherwise, all data collected from the
#    Tesla API is logged in a sqlite3 DB.
#
################################################################################

from __future__ import print_function
import argparse
import json
import os
import sqlite3
import sys
import time
import urllib2

import teslajson


DEF_CONFIGS_PATH = "./.teslas.yml"

INTER_CMD_DELAY = 0.1


def dictDiff(newDict, oldDict):
    '''Take a pair of dictionaries and return a four-tuple with the elements
       that are: added, removed, changed, and unchanged between the new
       and the old dicts.
       Inputs:
         newDict: dict whose content might have changed
         oldDict: dict that is being compared against

       Returns
         added: set of dicts that were added
         removed: set of dicts that were removed
         changed: set of dicts that were changed
         unchanged: set of dicts that were not changed
    '''
    inOld = set(oldDict)
    inNew = set(newDict)

    added = (inNew - inOld)
    removed = (inOld - inNew)

    common = inOld.intersection(inNew)

    changed = set(x for x in common if oldDict[x] != newDict[x])
    unchanged = (common - changed)

    return (added, removed, changed, unchanged)



#### TODO move this to 'tesla.py'
class Car(object):
    '''Car object that encapsulates the state of a car,
    '''
    def __init__(self, vin, config, vehicle):
        self.vin = vin
        self.config = config
        self.vehicle = vehicle

    def __str__(self):
        s = "VIN: {0}\n".format(self.vin)
        j = json.dumps(self.config, indent=4, sort_keys=True)
        s += "config: " + j + "\n"
        j = json.dumps(self.vehicle, indent=4, sort_keys=True)
        s += "vehicle: " + j + "\n"
        return s

    def _dataRequest(self, cmd, retries=3):
        r = None
        while True:
            try:
                r = self.vehicle.data_request(cmd)
            except urllib2.HTTPError as e:
                #### TODO better exception handler
                sys.stderr.write("WARNING: {0}\n".format(e))
                if e.code == 400:
                    return None
                elif e.code == 404:
                    return None
                retries -= 1
                if retries < 0:
                    return None
            if r:
                break
        return r

    def wakeUp(self):
        r = self.vehicle.wake_up()
        #### TODO add to DB
        return r['response']

    def getName(self):
        #### TODO add to DB
        return self.vehicle['display_name']

    def getChargeState(self):
        #### TODO add to DB
        return self._dataRequest('charge_state')

    def getClimateSettings(self):
        #### TODO add to DB
        return self._dataRequest('climate_state')

    def getDriveState(self):
        #### TODO add to DB
        return self._dataRequest('drive_state')

    def getGUISettings(self):
        #### TODO add to DB
        return self._dataRequest('gui_settings')

    def getVehicleState(self):
        #### TODO add to DB
        return self._dataRequest('vehicle_state')

    def getCarState(self):
        state = {}
        state['guiSettings'] = self.getGUISettings()
        time.sleep(INTER_CMD_DELAY)

        state['chargeState'] = self.getChargeState()
        time.sleep(INTER_CMD_DELAY)

        state['climageSettings'] = self.getClimateSettings()
        time.sleep(INTER_CMD_DELAY)

        state['vehicleState'] = self.getVehicleState()
        time.sleep(INTER_CMD_DELAY)

        state['driveState'] = self.getDriveState()
        return state


#
# MAIN
#
def main():
    # Print the given message, print the usage string, and exit with an error.
    def fatalError(msg):
        sys.stderr.write("Error: {0}\n".format(msg))
        sys.stderr.write("Usage: {0}\n".format(usage))
        sys.exit(1)

    usage = "Usage: {0} [-v] [-c <configsFile>] [-d <dbFile>] [-V <VIN>]"
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-c", "--configsFile", action="store", type=str,
        default=DEF_CONFIGS_PATH, help="path to file with configurations")
    ap.add_argument(
        "-d", "--dbFile", action="store", type=str,
        help="path to file that contains the log DB")
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
    if options.verbose > 3:
        json.dump(confs, sys.stdout, indent=4, sort_keys=True)    #### TMP TMP TMP
        print("")

    if options.VIN:
        carVINs = [options.VIN]
    else:
        carVINs = confs['CARS'].keys()
    if options.verbose > 2:
        print("CARS: {0}".format(carVINs))

    user = confs.get('USER')
    if not user:
        user = raw_input("user: ")
    if options.verbose > 2:
        print("USER: {0}".format(user))

    if options.password:
        password = options.password
    else:
        password = confs.get('PASSWD')
    if not password:
        password = raw_input("password: ")

    db = None
    dbFile = confs.get('DB')
    if options.dbFile:
        dbFile = options.dbFile
    if dbFile:
        if not os.path.exists(dbFile):
            fatalError("Invalid DB file: {0}".format(dbFile))
        db = sqlite3.connect(dbFile)
    else:
        if options.verbose:
            sys.stderr.write("WARNING: not logging data to DB")

    try:
        conn = teslajson.Connection(user, password)
    except Exception as e:
        fatalError("Failed to connect {0}".format(e))
    if options.verbose > 3:
        print("CONNECTION: {0}".format(conn))
        print("")

    if options.verbose > 2:
        print("Number of vehicles: {0}".format(len(conn.vehicles)))
        n = 1
        for v in conn.vehicles:
            print("Vehicle #{0}:".format(n), end='')
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

    if options.verbose > 1:
        print("Watching: {0}".format(vinList))
        notAskedFor = list(set(teslaVINs) - set(vinList))
        if notAskedFor:
            print("Cars Tesla API knows about, but not asked for: {0}".format(notAskedFor))

    vehicles = {v['vin']: v for v in conn.vehicles if v['vin'] in vinList}
    if options.verbose > 3:
        print("VEHICLES:")
        json.dump(vehicles, sys.stdout, indent=4, sort_keys=True)
        print("")

    cars = {}
    for vin in vinList:
        cars[vin] = Car(vin, confs['CARS'][vin], vehicles[vin])

        #### TODO check if a DB already exists for the given car, if not, create one, with all the Tables (one for every object from the Tesla API)

    for vin, car in cars.items():
        if options.verbose > 3:
            print("CAR: {0}".format(car))
        if options.verbose > 1:
            print("Waking up {0}".format(car.getName()))
        car.wakeUp()
        #### TODO add error handler
        time.sleep(INTER_CMD_DELAY)

        state = car.getCarState()
        #### TODO add error handler
        if options.verbose > 1:
            print("CarState: ", end='')
            json.dump(state, sys.stdout, indent=4, sort_keys=True)
            print("")
        time.sleep(INTER_CMD_DELAY)

        print("\n")

        #### TODO launch tracker threads for each car

    #### TODO cleanup
    if db:
        db.close()

if __name__ == '__main__':
    main()

"""
        r = car.getGUISettings()
        #### TODO add error handler
        if options.verbose > 1:
            print("GUISettings: ", end='')
            json.dump(r, sys.stdout, indent=4, sort_keys=True)
            print("")
        time.sleep(INTER_CMD_DELAY)

        r = car.getChargeState()
        #### TODO add error handler
        if options.verbose > 1:
            print("ChargeState: ", end='')
            json.dump(r, sys.stdout, indent=4, sort_keys=True)
            print("")
        time.sleep(INTER_CMD_DELAY)

        r = car.getClimateSettings()
        #### TODO add error handler
        if options.verbose > 1:
            print("ClimateSettings: ", end='')
            json.dump(r, sys.stdout, indent=4, sort_keys=True)
            print("")
        time.sleep(INTER_CMD_DELAY)

        r = car.getVehicleState()
        #### TODO add error handler
        if options.verbose > 1:
            print("VehicleState: ", end='')
            json.dump(r, sys.stdout, indent=4, sort_keys=True)
            print("")
        time.sleep(INTER_CMD_DELAY)

        r = car.getDriveState()
        #### TODO add error handler
        if options.verbose > 1:
            print("DriveState: ", end='')
            json.dump(r, sys.stdout, indent=4, sort_keys=True)
            print("")
        time.sleep(INTER_CMD_DELAY)
"""