'''
################################################################################
#
# Car Polling Process for TeslaWatch Application
#
################################################################################
'''

import time


def tracker(carObj, carDB, Q):
    ''' Per-car process that polls the Tesla API, logs the data, and emits
        notifications.

        ????

        Inputs
          carObj: Car object for the car to track
          carDB: CarDB object to log the data for the car being tracked
          Q: MP Queue object for returning status
    '''
    try:
        carName = carObj.getName()
        msg = "TRACKING {0}".format(carName)
        Q.put(msg)

        while True:
            #### TODO implement the poll loop
            time.sleep(30)
    except Exception as e:
        msg = "STOPPING {0}: {1}".format(carName, e)
        Q.put(msg)
    carDB.close()
