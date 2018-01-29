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
import logging
import multiprocessing as mp
import os
import Queue
import random
import signal
import sys
import time
import yaml

from notify import Notifier
from regions import Region
from teslaCar import Car
import teslaDB
from tracker import Tracker
import teslajson

'''
TODO:
  * convert all files over to use 'looging'
'''

# default path to configs file
DEF_CONFIGS_FILE = "./.teslas.yml"

# default path to DB schema file
DEF_SCHEMA_FILE = "./dbSchema.yml"

DEF_LOG_LEVEL = "WARNING"

# Default
# Includes intervals between samples of the Tesla API (quantized to integer
#  multiples of the min time), given in units of seconds, and thresholds
#### FIXME
#### TODO make more rational choices for these values
DEF_SETTINGS = {
    'intervals': {
        'chargeState': 5 * 60,
        'climateSettings': 10 * 60,
        'driveState': 1,
        'guiSettings': 3 * 60,
        'vehicleState': 60
    },
    'thresholds': {
        'distance': 0
    }
}


def commandInterpreter(trackers, cmdQs, respQs):
    ''' TBD
    '''
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
                print(dumpQueue(respQs[vin]))
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


def dictMerge(old, new):
    ''' Merge a new dict into an old one, updating the old one (recursively).
    '''
    for k, v in new.iteritems():
        if (k in old and isinstance(old[k], dict) and
            isinstance(new[k], collections.Mapping)):
            dictMerge(old[k], new[k])
        else:
            old[k] = new[k]


def dumpQueue(q):
    ''' Return the contents of a given message queue.
    '''
    result = []
    try:
        msg = q.get(True, 0.1)
        while msg:
            result.append(msg)
            msg = q.get(True, 0.1)
    except Queue.Empty:
        pass
    return result


#
# MAIN
#
def main():
    def fatalError(msg):
        ''' Print the given message, print the usage string, and exit with an error.
        '''
        sys.stderr.write("Error: {0}\n".format(msg))
        sys.stderr.write("Usage: {0}\n".format(usage))
        sys.exit(1)

    def signalHandler(sig, frame):
        ''' Catch SIGHUP to force a reload/restart and SIGINT to stop all.""
        '''
        if sig == signal.SIGHUP:
            print("SIGHUP")
            #### TODO stop, reload, and restart everything
        elif sig == signal.SIGINT:
            print("SIGINT")
            for q in cmdQs:
                q.send("STOP")

    usage = "Usage: {0} [-v] [-c <configsFile>] [-d <dbDir>] [-i] [-L <logLevel>] [-l <logFile>] [-p <passwd>] [-s <schemaFile>] [-V <VIN>]"
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
        "-L", "--logLevel", action="store", type=str, default=DEF_LOG_LEVEL,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level")
    ap.add_argument(
        "-l", "--logFile", action="store", type=str,
        help="Path to location of logfile (create it if it doesn't exist)")
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
    #### TODO validate config file against ./configSchema.yml, remove error checks and rely on this

    carVINs = confs['cars'].keys()
    if options.VIN:
        carVINs = [options.VIN]
    if not carVINs:
        fatalError("Must provide the VIN(s) of one or more car(s) to be tracked")
    if options.verbose > 2:
        print("cars: {0}".format(carVINs))

    user = confs.get('user')
    if not user:
        user = raw_input("user: ")
    if options.verbose > 2:
        print("user: {0}".format(user))

    password = confs.get('passwd')
    if options.password:
        password = options.password
    if not password:
        password = raw_input("password: ")

    logLevel = confs.get('logLevel')
    if options.logLevel:
        logLevel = options.logLevel

    logFile = confs.get('logFile')
    if options.logFile:
        logFile = options.logFile
    if not options.logLevel:
        l = getattr(logging, logLevel, None)
        #### TODO remove tests and rely on jsonschema validation
        if not isinstance(l, int):
            fatalError("Invalid log level: {0}\n".format(logLevel))
        logging.basicConfig(filename=logFile, level=l)

    schemaFile = confs.get('schema')
    if options.schemaFile:
        schemaFile = options.schemaFile
    if not os.path.isfile(schemaFile):
        fatalError("Invalid DB schema file: {0}".format(schemaFile))
    with open(schemaFile, "r") as f:
        schema = yaml.load(f)

    dbDir = confs.get('dbDir')
    if options.dbDir:
        dbDir = options.dbDir
    if dbDir:
        if not os.path.isdir(dbDir):
            fatalError("Invalid DB directory path: {0}".format(dbDir))
    else:
        if options.verbose:
            sys.stderr.write("WARNING: not logging data to DB\n")

    signal.signal(signal.SIGHUP, signalHandler)
    signal.signal(signal.SIGINT, signalHandler)

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
        conf = confs['cars'][vin]
        cars[vin] = car = Car(vin, conf, vehicles[vin])
        if options.verbose > 1:
            print("Waking up {0}: {1}".format(vin, car.getName()))
        if not car.wakeUp():
            if options.verbose > 1:
                print("Unable to wake up '{0}', skipping...".format(car.getName()))
            time.sleep(random.randint(5, 15))
            continue

        # give car time to wake up and dither start times across cars
        #### FIXME time.sleep(random.randint(15, 45))

        cdb = None
        if dbDir:
            dbFile = os.path.join(dbDir, vin + ".db")
            cdb = teslaDB.CarDB(vin, dbFile, schema)
        tables = schema['tables'].keys()
        settings = dict(DEF_SETTINGS)
        dictMerge(settings, confs.get('config', {}).get('settings', {}))
        regions = [Region(r) for r in conf.get('regions', [])]
        notifier = Notifier(confs.get('config', {}).get('eventNotifiers', {}))
        cmdQs[vin] = mp.Queue()
        respQs[vin] = mp.Queue()
        tracker = Tracker(car, cdb, tables, settings, regions, notifier,
                          cmdQs[vin], respQs[vin])
        tracker.run()  #### TMP TMP TMP
        sys.exit(1)    #### TMP TMP TMP

        trackers[vin] = mp.Process(target=tracker.run, args=())
        trackers[vin].start()

    if options.interactive:
        commandInterpreter(trackers, cmdQs, respQs)

    for vin in trackers:
        trackers[vin].join()

    if options.verbose > 1:
        for vin in trackers:
            print("Results for {0}: {1}".format(vin, dumpQueue(respQs[vin])))
            print("")

if __name__ == '__main__':
    main()
