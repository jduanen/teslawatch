'''
################################################################################
#
# Car Polling Process for TeslaWatch Application
#
################################################################################
'''

import Queue
import sys
import time
import traceback

from LatLon import (LatLon, Latitude, Longitude)

from regions import Region


'''
TODO
  * periodically (e.g., once a day) get all the settings
  * poll the location and manage transitions between parked (home/away), moving, and stopped states
  * generate parked->moving/stopped and parked/moving->stopped events
  * look for geofence entry/exit events
  * look for temperature events (too hot/cold)
  * look for doors/windows open/unlocked for period of time events
  * look for battery going below a threshold events
  * add callback arg for events
  * add arg with dict of all the callbacks for the events of interest and the parameters for that type of event
  * make hooks that can call arbitrary functions in addition to sending messages on events
    - allow automation of locking/shutting/turning on/off climate, opening/closing stuff
  * specify functions to call (potentially external/shell cmds, in addition to those in events.py) in configs file
  * make separate poll rate/interval for each table
  * up the poll rate for drive state when moving to more frequent, less when stopped/parked
  * poll frequency: driveState (D/R vs P), vehicleState, chargeState, {climateSettings, guiSettings}
  * make the tracker keep track of previous states, detect transitions, and call the event object (with args relevent to the event)
    - create list of event/arg tuples and send to eventHandler object for the car
      * instantiate per-car eventHandler object in main loop and pass in as arg to the tracker
    - generate all events when this first starts up
  * instantiate a new location object everytime get a new location from the driveState API
    - check if new location entered/exited a region
    - create (home/work) regions from config spec, add new regions through various means
    - location object encapsulates lat/lon, computes distances, give it list of region objects and get back boolean vector (inside/outside)
    - keep track of regions here and detect transitions when new location given
  * do compression -- keep last contents of each table, and suppress db store if no change (ignore/mask timestamps)

Questions
  * make an event object that gets instantiated with params from the config file?
  * allow change of events/event parameters while continuing to run the tracker, or start a new tracker?

EVENT TYPES: all events qualified by day-of-week and time-of-day ranges
  * location state transition events
    - parked->moving/stopped
    - parked/moving->stopped
  * geofence events (specify set of different types of geofence regions)
    - enter region
    - exit region
  * temperature excursions
    - dropped below low threshold
    - rose above high threshold
  * door/window/sunroof open/unlocked while parked, for greater than threshold of time
  * battery level goes below a given threshold
'''

# commands that can be sent on the trackers' command Queue
TRACKER_CMDS = ("PAUSE", "RESUME", "STOP")


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


class Tracker(object):
    ''' Object that encapsulates all of the state associated with a car that is being tracked
    '''
    def __init__(self, carObj, carDB, tables, settings, regions, notifier, inQ, outQ):
        ''' Construct a tracker object

            Inputs
              carObj: Car object for the car to track
              carDB: CarDB object to log the data for the car being tracked
              tables: ????
              settings: ????
              regions: ????
              notifier: ????
              inQ: MP Queue object for receiving commands from the master
              outQ: MP Queue object for returning status
        '''
        self.car = carObj
        self.db = carDB
        self.tables = tables
        self.settings = settings
        self.intervals = settings['intervals']
        self.regions = regions
        self.notifier = notifier
        self.inQ = inQ
        self.outQ = outQ

        self.samples = {t: {'sample': {}, 'time': None} for t in tables}

    def run(self):
        ''' Per-car process that polls the Tesla API, logs the data, and emits
            notifications.

            This is intended to be called by Multiprocessing.Process()
        '''
        CHANGING_FIELDS = set(['timestamp', 'gps_as_of'])
        now = int(time.time())

        try:
            state = self.car.getCarState()
            if self.db:
                self.db.insertState(state)
            prevLoc = LatLon(state['driveState']['latitude'],
                             state['driveState']['longitude'])
            for tableName in self.samples:
                self.samples[tableName]['sample'] = state[tableName]
                self.samples[tableName]['time'] = now

            carName = self.car.getName()
            self.outQ.put("TRACKING {0}".format(carName))

            while True:
                try:
                    cmd = self.inQ.get_nowait()
                    if cmd == "STOP":
                        self.outQ.put("STOPPING {0}".format(carName))
                        break
                    elif cmd == "PAUSE":
                        cmd = self.inQ.get()
                        while cmd != "RESUME":
                            cmd = self.inQ.get()
                    elif cmd == "RESUME":
                        pass
                    else:
                        sys.stderr.write("WARNING: unknown tracker command '{0}'".format(cmd))
                except Queue.Empty:
                    pass

                #### TODO implement the poll loop
                #### TODO get current Location object, create vector of In-Region booleans, compute other events, call notifier for events
                curTime = int(time.time())
                for tableName in self.samples:
                    if curTime >= self.samples[tableName]['time'] + self.intervals[tableName]:
                        sample = self.car.getTable(tableName)
                        print("SAMPLE: {0}".format(tableName))
                        add, rem, chg, _ = dictDiff(self.samples[tableName]['sample'], sample)
                        if self.db:
                            if add or rem:
                                self.outQ.put("Table {0} Schema Change: ADD={1}, REM={2}".
                                              format(tableName, add, rem))
                            if not chg - CHANGING_FIELDS:
                                print("WRITE TO DB")   #### TMP TMP TMP
                                self.db.insertRow(tableName, sample)

                        if tableName == 'driveState':
                            newLoc = LatLon(sample['latitude'], sample['longitude'])
                            dist = newLoc.distance(prevLoc)
                            print(dist) #### TMP TMP TMP
                            if dist > self.settings['thresholds']['distance']:
                                print("MOVED: {0}".format(dist))

                        self.samples[tableName]['sample'] = sample
                        self.samples[tableName]['time'] = curTime

                #### TODO make the polling interval a function of the car's state
                ####      poll more frequently when driving and less when parked
                print("SLEEP")
                nextInterval = 1.0    #### TMP TMP TMP
                time.sleep(nextInterval)

        except Exception as e:
            traceback.print_exc()
            self.outQ.put("BAILING {0}: {1}".format(carName, e))
        if self.db:
            self.db.close()
