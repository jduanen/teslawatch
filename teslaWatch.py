#!/usr/bin/env python
'''
################################################################################
#
# Script to watch for Tesla state changes
#
# This is to run in the cloud and there will be an Android front-end to
#  manage the fences and this will issue notifications to the mobile device.
#
# N.B.
#  * Values given on command line override those in the config file.
#  * If no DB directory path is given (in either the config file or on the
#    command line) then nothing is logged to the DB.  Otherwise, all data
#    collected from the Tesla API is logged in a sqlite3 DB -- one file
#    for each car in the given DB directory, named with each car's VIN.
#
################################################################################
'''

from __future__ import print_function
import argparse
import json
import multiprocessing as mp
import os
import random
import signal
import sys
import time
import yaml

from teslaCar import Car
import teslaDB
from tracker import tracker
import teslajson


# default path to configs file
DEF_CONFIGS_FILE = "./.teslas.yml"

# default path to DB schema file
DEF_SCHEMA_FILE = "./schema.yml"


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


def commandInterpreter(trackers, cmdQs, respQs):
    #### TODO implement cmd interpreter and send cmds to running trackers to restart them and change their events
    cmd = ""
    while True:
        line = raw_input("> ")
        words = line.split(' ')
        cmd = words[0].lower().strip()
        args = words[1:]
        if cmd == 'l':
            print("Tracking: {0}".format(trackers.keys()))
        if cmd == 'p':
            vin = args[0]
            if vin not in trackers:
                print("ERROR: VIN '{0}' not being tracked".format(vin))
            else:
                dumpQueue(respQs[vin])
        if cmd == 'r':
            pass
        if cmd == 's':
            vin = args[0]
            if vin not in trackers:
                print("ERROR: VIN '{0}' not being tracked".format(vin))
            else:
                cmdQs[vin].put("STOP")
                #### TODO reread trackers
        elif cmd == 'q':
            break
        elif cmd == '?' or cmd == 'h':
            print("Help:")
            print("    h: print this help message")
            print("    l: show VINs of cars being tracked")
            print("    p <vin>: print output from car given by <vin>")
            print("    r: stop and restart all trackers, re-reading the configs file")
            print("    s <vin>: stop tracking the car given by <vin>")
            print("    q: quit")
            print("    ?: print this help message")
    return


def dumpQueue(q):
    result = []
    for msg in iter(q.get, 'STOP'):
        result.append(msg)
    time.sleep(.1)
    return result


def signalHandler(sig, frame):
    if sig == signal.SIGHUP:
        print("SIGHUP")
        #### TODO stop, reload, and restart everything


#
# MAIN
#
def main():
    # Print the given message, print the usage string, and exit with an error.
    def fatalError(msg):
        sys.stderr.write("Error: {0}\n".format(msg))
        sys.stderr.write("Usage: {0}\n".format(usage))
        sys.exit(1)

    usage = "Usage: {0} [-v] [-c <configsFile>] [-d <dbDir>] [-i] [-p <passwd>] [-s <schemaFile>] [-V <VIN>]"
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-c", "--configsFile", action="store", type=str,
        default=DEF_CONFIGS_FILE, help="path to file with configurations")
    ap.add_argument(
        "-d", "--dbDir", action="store", type=str,
        help="path to a directory that contains the DB files for cars")
    ap.add_argument(
        "-i", "--interactive", action="store_true", default=False,
        help="enable interactive mode")
    ap.add_argument(
        "-p", "--password", action="store", type=str, help="user password")
    ap.add_argument(
        "-s", "--schemaFile", action="store", type=str, default=DEF_SCHEMA_FILE,
        help="path to the JSON Schema file that describes the DB's tables")
    ap.add_argument(
        "-V", "--VIN", action="store", type=str,
        help="VIN of car to use (defaults to all found in config file")
    ap.add_argument(
        "-v", "--verbose", action="count", default=0, help="print debug info")
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

    dbDir = confs.get('DB_DIR')
    schemaFile = confs.get('SCHEMA')
    if options.dbDir:
        dbDir = options.dbDir
    if dbDir:
        if not os.path.isdir(dbDir):
            fatalError("Invalid DB directory path: {0}".format(dbDir))
        if options.schemaFile:
            schemaFile = options.schemaFile
        if not os.path.isfile(schemaFile):
            fatalError("Invalid DB schema file: {0}".format(schemaFile))
    else:
        if options.verbose:
            sys.stderr.write("WARNING: not logging data to DB\n")

    signal.signal(signal.SIGHUP, signalHandler)

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
    cmdQs = {}
    respQs = {}
    trackers = {}
    for vin in vinList:
        cars[vin] = car = Car(vin, confs['CARS'][vin], vehicles[vin])
        if options.verbose > 1:
            print("Waking up {0}".format(car.getName()))
        car.wakeUp()
        #### TODO add error handler

        time.sleep(random.randint(15, 45))

        state = car.getCarState()
        #### TODO add error handler
        if options.verbose > 1:
            print("CarState: ", end='')
            json.dump(state, sys.stdout, indent=4, sort_keys=True)
            print("")

        cdb = None
        if dbDir and schemaFile:
            dbFile = os.path.join(dbDir, vin + ".db")
            cdb = teslaDB.CarDB(vin, dbFile, schemaFile)
        cmdQs[vin] = mp.Queue()
        respQs[vin] = mp.Queue()
        trackers[vin] = mp.Process(target=tracker, args=(car, cdb, cmdQs[vin], respQs[vin]))
        trackers[vin].start()

    if options.interactive:
        commandInterpreter(trackers, cmdQs, respQs)

    for vin in trackers:
        trackers[vin].join()

    if options.verbose > 1:
        for vin in trackers:
            print("Results for {0}:".format(vin))
            dumpQueue(respQs[vin])
            print("")

if __name__ == '__main__':
    main()
