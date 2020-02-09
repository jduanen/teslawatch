'''
################################################################################
#
# Car object definition for TeslaWatch Application
#
################################################################################
'''

import json
import sys
import time
##from urllib import HTTPError


INTER_CMD_DELAY = 0.1

# map the car DB schema name to the Tesla API name
TABLES_NAME_MAP = {
    'chargeState': "charge_state",
    'climateState': "climate_state",
    'driveState': "drive_state",
    'guiSettings': "gui_settings",
    'vehicleState': "vehicle_state"
}


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
##            except HTTPError as e:
            except Exception as e:
                #### TODO better exception handler
                sys.stderr.write("WARNING: {0}\n".format(e))
                if e.code == 400:
                    return None
                elif e.code == 404:
                    return None
                retries -= 1
                if retries < 0:
                    return None
                time.sleep(3)
            if r:
                break
        return r

    def wakeUp(self):
        ''' Wakeup car'''
        try:
            r = self.vehicle.wake_up()
        except Exception as e:
            sys.stderr.write("WARNING: failed to wake up car '{0}': {1}\n".format(self.vin, e))
            return None
        #### TODO check for error response: print warning and return None
        return r['response']

    def getName(self):
        ''' Return car's name'''
        return self.vehicle['display_name']

    def getTable(self, tableName):
        ''' Take the name of a table in the Tesla API and return it as a dict.

            Inputs
                tableName: name of one of the Tesla API's state tables

            Returns
                dict with contents of desired table, or None if error
        '''
        if tableName not in TABLES_NAME_MAP.keys():
            sys.stderr.write("ERROR: invalid table name '{0}'".format(tableName))
            return None
        return self._dataRequest(TABLES_NAME_MAP[tableName])

    def getChargeState(self):
        ''' Get the car's charge state'''
        return self._dataRequest('charge_state')

    def getClimateSettings(self):
        ''' Get the car's climate settings'''
        return self._dataRequest('climate_state')

    def getDriveState(self):
        ''' Get the car's drive state and location'''
        return self._dataRequest('drive_state')

    def getGUISettings(self):
        ''' Get the car's GUI settings'''
        return self._dataRequest('gui_settings')

    def getVehicleState(self):
        ''' Get the vehicle state for the car'''
        return self._dataRequest('vehicle_state')

    def getCarState(self):
        ''' Get all of the state records for the car from the Tesla API and
            return them in a dict, with the tables' names as keys.
        '''
        state = {}
        state['guiSettings'] = self.getGUISettings()
        time.sleep(INTER_CMD_DELAY)

        state['chargeState'] = self.getChargeState()
        time.sleep(INTER_CMD_DELAY)

        state['climateSettings'] = self.getClimateSettings()
        time.sleep(INTER_CMD_DELAY)

        state['vehicleState'] = self.getVehicleState()
        time.sleep(INTER_CMD_DELAY)

        state['driveState'] = self.getDriveState()
        return state

#
# TESTING
#
if __name__ == '__main__':
    #### TODO implement test cases
    pass
