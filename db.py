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


DEF_SCHEMA_FILE = "./schema.yml"

DUMMY_VIN = "5YJSA1H10EFP00000"


class CarDB(object):
    TYPE_MAP = {
        'integer': "INTEGER",
        'number': "REAL",
        'boolean': "INTEGER",
        'string': "TEXT"
    }
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

        if not os.path.exists(schemaFile):
            raise ValueError("Schema file not found: {0}".format(schemaFile))
        try:
            with open(schemaFile, "r") as f:
                self.schema = yaml.load(f)
        except IOError:
            raise
        except:
            raise ValueError("Unable to read schema file: {0}".format(schemaFile))

        #### TODO validate schema version

        if 'tables' not in self.schema:
            raise Exception("'tables' field missing from schema file: {0}".format(schemaFile))
        for tableName in self.schema['tables'].keys():
            cols = "id INTEGER PRIMARY KEY"
            keyList = self.schema['tables'][tableName]['properties'].keys()
            keyList.sort()
            for colName in keyList:
                colType = CarDB.TYPE_MAP[self.schema['tables'][tableName]['properties'][colName]['type']]
                cols += ", {0} {1}".format(colName, colType)
            tableDef = "CREATE TABLE IF NOT EXISTS {0} ({1});".format(tableName, cols)
            self.createTable(tableName, tableDef)

        '''
    'guiSettings': """ CREATE TABLE IF NOT EXISTS guiSettings (
        id INTEGER PRIMARY KEY,
        gui_24_hour_time INTEGER,
        gui_charge_rate_units TEXT,
        gui_distance_units TEXT,
        gui_range_display TEXT,
        gui_temperature_units TEXT,
        timestamp INTEGER);""",
        '''

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
        cols = ", ".join('"{}"'.format(col) for col in row.keys())
        vals = ", ".join(':{}'.format(col) for col in row.keys())
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

    usage = "Usage: {0} [-v] [-s <scheaFile>] <dbFile>"
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-s", "--schemaFile", action="store", type=str, default=DEF_SCHEMA_FILE,
        help="path to the JSON Schema file that describes the DB's tables")
    ap.add_argument(
        "-v", "--verbose", action="count", default=0, help="print debug info")
    ap.add_argument(
        "dbFile", action="store", type=str,
        help="path to a test Sqlite3 DB file")
    options = ap.parse_args()

    if not options.dbFile:
        fatalError("Must provide test DB file")

    with CarDB(DUMMY_VIN, options.dbFile, options.schemaFile) as cdb:
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
