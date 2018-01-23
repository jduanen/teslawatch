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

from location import Location
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

# Intervals between samples of the Tesla API (quantized to integer multiples
#  of the min time), given in units of seconds.
#### TODO make more rational choices for these values
intervals = {
    'chargeState': 5 * 60,
    'climateSettings': 10 * 60,
    'driveStateD': 1,
    'driveStateP': 30,
    'guiSettings': 3 * 60,
    'vehicleState': 60
}

# commands that can be sent on the trackers' command Queue
TRACKER_CMDS = ("PAUSE", "RESUME", "STOP")


def tracker(carObj, carDB, regions, notifier, inQ, outQ):
    ''' Per-car process that polls the Tesla API, logs the data, and emits
        notifications.

        ????

        Inputs
          carObj: Car object for the car to track
          carDB: CarDB object to log the data for the car being tracked
          regions: ????
          notifier: ????
          inQ: MP Queue object for receiving commands from the master
          outQ: MP Queue object for returning status
    '''
    state = carObj.getCarState()
    if carDB:
        carDB.insertState(state)
    now = int(time.time())
    lastSampled = {
        'chargeState': now,
        'climateSettings': now,
        'driveStateD': now,
        'driveStateP': now,
        'guiSettings': now,
        'vehicleState': now
    }
    prevLoc = Location(state['driveState']['latitude'], state['driveState']['longitude'])
    try:
        carName = carObj.getName()
        msg = "TRACKING {0}".format(carName)
        outQ.put(msg)

        lastFullSample = int(time.time())

        while True:
            try:
                cmd = inQ.get_nowait()
                if cmd == "STOP":
                    msg = "STOPPING {0}".format(carName)
                    outQ.put(msg)
                    break
                elif cmd == "PAUSE":
                    cmd = inQ.get()
                    while cmd != "RESUME":
                        cmd = inQ.get()
                elif cmd == "RESUME":
                    pass
                else:
                    sys.stderr.write("WARNING: unknown tracker command '{0}'".format(cmd))
            except Queue.Empty:
                pass

            #### TODO implement the poll loop
            #### TEMP TEMP TEMP
            #### FIXME use the per-dict intervals and lastSampled times
            #### TODO get current Location object, create vector of In-Region booleans, compute other events, call notifier for events
            curTime = int(time.time())
            if curTime > (lastFullSample + FULL_SAMPLE_INTERVAL):
                state = carObj.getCarState()
                if carDB:
                    carDB.insertState(state)
                lastFullSample = curTime
            else:
                sample = carObj.getDriveState()
                if carDB:
                    carDB.insertRow('driveState', sample)

            #### TODO make the polling interval a function of the car's state -- poll more frequently when driving and less when parked
            time.sleep(LOCATION_SAMPLE_INTERVAL)

    except Exception as e:
        msg = "BAILING {0}: {1}".format(carName, e)
        outQ.put(msg)
    carDB.close()
