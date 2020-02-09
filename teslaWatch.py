#!/usr/bin/env python3
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

#### TODO add logging

import argparse
import collections
import json
import logging
import multiprocessing as mp
import os
import queue
import random
import signal
import sys
import time

import yaml

from notifier import Notifier
from regions import Region
from teslaCar import Car
import teslaDB
import teslajson
from teslawatch import fatalError, dictMerge
from tracker import Tracker

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


def commandInterpreter(trackers, cmds, resps):
    ''' TBD
    '''
    #### TODO implement cmd interpreter and send cmds to running trackers to restart them and change their events
    cmd = ""
    while True:
        line = input("> ")
        words = line.split(' ')
        cmd = words[0].lower().strip()
        args = words[1:]
        if cmd == 'l':
            print(f"Tracking: {trackers.keys()}")
        if cmd == 'p':
            vin = args[0]
            if vin not in trackers:
                print(f"ERROR: VIN '{vin}' not being tracked")
            else:
                print(dumpQueue(resps[vin]))
        if cmd == 'r':
            pass
        if cmd == 's':
            vin = args[0]
            if vin not in trackers:
                print(f"ERROR: VIN '{vin}' not being tracked")
            else:
                cmds[vin].put("STOP")
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
    ''' Return the contents of a given message queue.
    '''
    result = []
    try:
        msg = q.get(True, 0.1)
        while msg:
            result.append(msg)
            msg = q.get(True, 0.1)
    except queue.Empty:
        pass
    return result


def run(options):
    try:
        conn = teslajson.Connection(options.user, options.password)
    except Exception as e:
        fatalError(f"Failed to connect: {e}")
    logging.info(f"Connection: {conn}")

    logging.info(f"Number of vehicles: {len(conn.vehicles)}")
    if options.verbose > 1:
        n = 1
        for v in conn.vehicles:
            print(f"Vehicle #{n}:", end='')
            json.dump(v, sys.stdout, indent=4, sort_keys=True)
            print("")
            n += 1

    carVINs = opts.confs['cars'].keys()
    if opts.VIN:
        carVINs = [opts.VIN]
    if not carVINs:
        fatalError("Must provide the VIN(s) of one or more car(s) to be tracked")
    logging.debug(f"cars: {carVINs}")

    teslaVINs = [v['vin'] for v in conn.vehicles]
    vinList = [v for v in teslaVINs if v in carVINs]
    if not vinList:
        fatalError("Unable to find requested cars in Tesla API")

    notFound = list(set(carVINs) - set(vinList))
    if notFound:
        fatalError(f"Cars asked for, but not found in Tesla API: {notFound}")

    logging.debug(f"Watching: {vinList}")
    notAskedFor = list(set(teslaVINs) - set(vinList))
    if notAskedFor:
        logging.warning(f"Cars Tesla API knows about, but not asked for: {notAskedFor}")

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
        conf = opts.confs['cars'][vin]
        cars[vin] = car = Car(vin, conf, vehicles[vin])
        logging.info("Waking up {vin}: {car.getName()}")
        if not car.wakeUp():
            logging.warning(f"Unable to wake up '{car.getName()}', skipping...")
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
        dictMerge(settings, opts.confs.get('config', {}).get('settings', {}))
        regions = [Region(r) for r in conf.get('regions', [])]
        notifier = Notifier(opts.confs.get('config', {}).get('eventNotifiers', {}))
        cmdQs[vin] = mp.Queue()
        respQs[vin] = mp.Queue()
        tracker = Tracker(car, cdb, tables, settings, regions, notifier,
                          cmdQs[vin], respQs[vin])
        logging.info(f"Tracker: {vin}")
        trackers[vin] = mp.Process(target=tracker.run, args=())

    for vin in trackers:
        trackers[vin].start()

    if options.interactive:
        commandInterpreter(trackers, cmdQs, respQs)

    for vin in trackers:
        trackers[vin].join()
        logging.debug(f"Results for {vin}: {dumpQueue(respQs[vin])}")


def getOps():
    def signalHandler(sig, frame):
        ''' Catch SIGHUP to force a reload/restart and SIGINT to stop all.""
        '''
        if sig == signal.SIGHUP:
            logging.info("SIGHUP")
            #### TODO stop, reload, and restart everything
        elif sig == signal.SIGINT:
            logging.info("SIGINT")
            for vin in cmdQs:
                logging.debug(f"Stopping: {vin}")
                cmdQs[vin].put("STOP")

    usage = f"Usage: {sys.argv[0]} [-v] [-c <configsFile>] [-d <dbDir>] [-i] [-L <logLevel>] [-l <logFile>] [-p <passwd>] [-s <schemaFile>] [-V <VIN>]"
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
    opts = ap.parse_args()

    if not os.path.exists(opts.configsFile):
        fatalError(f"Invalid configuration file: {opts.configsFile}")

    #### TODO add check if configs file has proper protections

    with open(opts.configsFile, "r") as confsFile:
        confs = list(yaml.load_all(confsFile, Loader=yaml.Loader))[0]
    if opts.verbose > 3:
        json.dump(confs, sys.stdout, indent=4, sort_keys=True)    #### TMP TMP TMP
        print("")
    #### TODO validate config file against ./configSchema.yml, remove error checks and rely on this

    if opts.logLevel:
        confs['config']['logLevel'] = opts.logLevel
    else:
        if 'logLevel' not in confs['config']:
            confs['config']['logLevel'] = DEF_LOG_LEVEL
    logLevel = confs['config']['logLevel']
    l = getattr(logging, logLevel, None)
    if not isinstance(l, int):
        fatalError(f"Invalid log level: {logLevel}")

    if opts.logFile:
        confs['config']['logFile'] = opts.logFile
    logFile = confs['config'].get('logFile')
    if opts.verbose:
        print(f"Logging to: {logFile}")
    if logFile:
        logging.basicConfig(filename=logFile, level=l)
    else:
        logging.basicConfig(level=l)

    opts.user = confs.get('user')
    if not opts.user:
        input("user: ")
    logging.debug(f"user: {opts.user}")

    # N.B. precedence order: command line options then config file inputs.
    #      if neither given, then propmt user for console input
    if opts.password:
        password = opts.password
    else:
        password = confs.get('passwd')
    if not password:
        password = input("password: ")

    if opts.schemaFile:
        schemaFile = opts.schemaFile
    else:
        schemaFile = confs.get('schema')
    if not os.path.isfile(schemaFile):
        fatalError(f"Invalid DB schema file: {schemaFile}")
    with open(schemaFile, "r") as f:
        schema = yaml.load(f, Loader=yaml.Loader)

    if opts.dbDir:
        dbDir = opts.dbDir
    else:
        dbDir = confs.get('dbDir')
    if dbDir:
        if not os.path.isdir(dbDir):
            fatalError(f"Invalid DB directory path: {dbDir}")
    else:
        if opts.verbose:
            logging.warning("Not logging data to DB")

    signal.signal(signal.SIGHUP, signalHandler)
    signal.signal(signal.SIGINT, signalHandler)

    opts.confs = confs
    return opts


if __name__ == '__main__':
    opts = getOps()
    run(opts)
