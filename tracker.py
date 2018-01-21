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

# number of seconds between location samples
LOCATION_SAMPLE_INTERVAL = 5 * 60    # 5 mins

# number of seconds between complete samples (must be greater than LOCATION_SAMPLE_INTERVAL)
FULL_SAMPLE_INTERVAL = (3 * LOCATION_SAMPLE_INTERVAL)    # 15mins


# commands that can be sent on the trackers' command Queue
TRACKER_CMDS = ("PAUSE", "RESUME", "STOP")


def tracker(carObj, carDB, inQ, outQ):
    ''' Per-car process that polls the Tesla API, logs the data, and emits
        notifications.

        ????

        Inputs
          carObj: Car object for the car to track
          carDB: CarDB object to log the data for the car being tracked
          inQ: MP Queue object for receiving commands from the master
          outQ: MP Queue object for returning status
    '''
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
            time.sleep(LOCATION_SAMPLE_INTERVAL)

    except Exception as e:
        msg = "BAILING {0}: {1}".format(carName, e)
        outQ.put(msg)
    carDB.close()
