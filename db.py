################################################################################
#
# Sqlite3 DB Library for TeslaWatch Application
#
################################################################################


from __future__ import print_function
import argparse
import json
import os
import sqlite3
import sys
import yaml


#### TODO
####  * Version the schema and put in checks
####  * Change the TABLES struct into external yaml file with versioning, read it in and construct the sql cmds on the fly


DUMMY_VIN = "5YJSA1H10EFP00000"

TABLES = {
    'guiSettings': """ CREATE TABLE IF NOT EXISTS guiSettings (
        id INTEGER PRIMARY KEY,
        gui_24_hour_time INTEGER,
        gui_charge_rate_units TEXT,
        gui_distance_units TEXT,
        gui_range_display TEXT,
        gui_temperature_units TEXT,
        timestamp INTEGER);""",
    'chargeState': """ CREATE TABLE IF NOT EXISTS chargeState (
        id INTEGER PRIMARY KEY,
        battery_heater_on INTEGER,
        battery_level INTEGER,
        battery_range REAL,
        charge_current_request INTEGER,
        charge_current_request_max INTEGER,
        charge_enable_request INTEGER,
        charge_energy_added REAL,
        charge_limit_soc INTEGER,
        charge_limit_soc_max INTEGER,
        charge_limit_soc_min INTEGER,
        charge_limit_soc_std INTEGER,
        charge_miles_added_ideal REAL,
        charge_miles_added_rated REAL,
        charge_port_door_open INTEGER,
        charge_port_latch TEXT,
        charge_rate REAL,
        charge_to_max_range INTEGER,
        charger_actual_current INTEGER,
        charger_phases NULL,
        charger_pilot_current INTEGER,
        charger_power INTEGER,
        charger_voltage INTEGER,
        charging_state TEXT,
        conn_charge_cable TEXT,
        est_battery_range REAL,
        fast_charger_brand TEXT,
        fast_charger_present INTEGER,
        fast_charger_type TEXT,
        ideal_battery_range REAL,
        managed_charging_active INTEGER,
        managed_charging_start_time TEXT,
        managed_charging_user_canceled INTEGER,
        max_range_charge_counter INTEGER,
        not_enough_power_to_heat INTEGER,
        scheduled_charging_pending INTEGER,
        scheduled_charging_start_time INTEGER,
        time_to_full_charge REAL,
        timestamp INTEGER,
        trip_charging INTEGER,
        usable_battery_level INTEGER,
        user_charge_enable_request INTEGER);""",
    'climateSettings': """ CREATE TABLE IF NOT EXISTS climateSettings (
        id INTEGER PRIMARY KEY,
        battery_heater INTEGER,
        battery_heater_no_power INTEGER,
        driver_temp_setting REAL,
        fan_status INTEGER,
        inside_temp REAL,
        is_auto_conditioning_on INTEGER,
        is_climate_on INTEGER,
        is_front_defroster_on INTEGER,
        is_preconditioning INTEGER,
        is_rear_defroster_on INTEGER,
        left_temp_direction INTEGER,
        max_avail_temp REAL,
        min_avail_temp REAL,
        outside_temp REAL,
        passenger_temp_setting REAL,
        right_temp_direction INTEGER,
        seat_heater_left INTEGER,
        seat_heater_rear_center INTEGER,
        seat_heater_rear_left INTEGER,
        seat_heater_rear_left_back INTEGER,
        seat_heater_rear_right INTEGER,
        seat_heater_rear_right_back INTEGER,
        seat_heater_right INTEGER,
        smart_preconditioning INTEGER,
        timestamp INTEGER);""",
    'vehicleState': """ CREATE TABLE IF NOT EXISTS vehicleState (
        id INTEGER PRIMARY KEY,
        api_version INTEGER,
        autopark_state TEXT,
        autopark_state_v2 TEXT,
        calendar_supported INTEGER,
        car_version TEXT,
        center_display_state INTEGER,
        df INTEGER,
        dr INTEGER,
        ft INTEGER,
        locked INTEGER,
        notifications_supported INTEGER,
        odometer REAL,
        parsed_calendar_supported INTEGER,
        pf INTEGER,
        pr INTEGER,
        remote_start INTEGER,
        remote_start_supported INTEGER,
        rt INTEGER,
        sun_roof_percent_open NULL,
        sun_roof_state TEXT,
        timestamp INTEGER,
        valet_mode INTEGER,
        valet_pin_needed INTEGER,
        vehicle_name TEXT);""",
    'driveState': """ CREATE TABLE IF NOT EXISTS driveState (
        id INTEGER PRIMARY KEY,
        gps_as_of INTEGER,
        heading INTEGER,
        latitude REAL,
        longitude REAL,
        power INTEGER,
        shift_state NULL,
        speed NULL,
        timestamp INTEGER);"""
}


class CarDB(object):
    '''Object that encapsulates the Sqlite3 DB that contains data from a car,
    '''
    def __init__(self, vin, dbFile, schemaFile, create=True):
        ''' Instantiate a DB object for the car given by the VIN and connect to
            the given DB file.

            Inputs
                vin: VIN string for a car
                dbFile: Path to a Sqlite3 DB file (created if doesn't exist)
                schemaFile: Path to a YAML file that contains the schema for
                    all of the tables in the DB
                create: If True, creates file if not found, otherwise fails if
                    file not found.
            Returns
                car DB object
        '''
        self.vin = vin

        if not create:
            if not os.path.exists(dbFile):
                raise ValueError("Invalid DB file: {0}".format(dbFile))
        self.dbFile = dbFile

        self.db = sqlite3.connect(dbFile)
        self.cursors = {}

        #### TODO read and parse JSON Schema and set up tables schema struct
        #### FIXME generate 'tableDef' on the fly from the JSON schema

        for tableName, tableDef in TABLES.iteritems():
            self.createTable(tableName, tableDef)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.db.close()

    def createTable(self, tableName, tableDef):
        if options.verbose > 2:
            print("{0}: ".format(tableName))
            json.dump(tableDef, sys.stdout, indent=4, sort_keys=True)
            print("")
        self.cursors[tableName] = None
        c = self.db.cursor()
        c.execute(tableDef)
        self.db.commit()

    def getTable(self, tableName):
        c = self.db.cursor()
        sqlCmd = "SELECT * FROM {0};".format(tableName)
        table = c.execute(sqlCmd).fetchall()
        return table

    def getTables(self):
        tables = {}
        for tableName in self.getTableNames():
            tables[tableName] = self.getTable(tableName)
        return tables

    def getTableNames(self):
        c = self.db.cursor()
        sqlCmd = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        r = c.execute(sqlCmd).fetchall()
        return (str(t[0]) for t in r)

    def insertRow(self, tableName, row):
        c = self.db.cursor()
        cols = ', '.join('"{}"'.format(col) for col in row.keys())
        vals = ', '.join(':{}'.format(col) for col in row.keys())
        sqlCmd = 'INSERT INTO "{0}" ({1}) VALUES ({2})'.format(tableName, cols, vals)
        c.execute(sqlCmd, row)
        self.db.commit()

    def getRows(self, tableName):
        self.cursors[tableName] = self.db.cursor()
        sqlCmd = "SELECT * FROM {0};".format(tableName)
        self.cursors[tableName].execute(sqlCmd)
        return self.cursors[tableName]


#
# TESTING
#
if __name__ == '__main__':
    # Print the given message, print the usage string, and exit with an error.
    def fatalError(msg):
        sys.stderr.write("Error: {0}\n".format(msg))
        sys.stderr.write("Usage: {0}\n".format(usage))
        sys.exit(1)

    usage = "Usage: {0} [-v] <dbFile>"
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "dbFile", action="store", type=str,
        help="path to a test Sqlite3 DB file")
    ap.add_argument(
        "-v", "--verbose", action="count", default=0, help="print debug info")
    options = ap.parse_args()

    if not options.dbFile:
        fatalError("Must provide test DB file")

    with CarDB(DUMMY_VIN, options.dbFile) as cdb:
        tables = cdb.getTables()
        print("Tables: {0}".format(tables))

        if 'driveState' not in tables:
            fatalError("'driveState' table not found")

        dsTable = cdb.getTable('driveState')
        if options.verbose:
            print("driveState: ", end='')
            json.dump(dsTable, sys.stdout, indent=4, sort_keys=True)
            print("")

        driveStateData = {
            "gps_as_of": 1516343640,
            "heading": 258,
            "latitude": 37.460213,
            "longitude": -122.166181,
            "power": 0,
            "shift_state": None,
            "speed": None,
            "timestamp": 1516343642013
        }
        cdb.insertRow('driveState', driveStateData)

        dsTable = cdb.getTable('driveState')
        if options.verbose:
            print("driveState: ", end='')
            json.dump(dsTable, sys.stdout, indent=4, sort_keys=True)
            print("")

        for row in cdb.getRows('driveState'):
            print(row)
