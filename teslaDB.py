'''
################################################################################
#
# Sqlite3 DB Library for TeslaWatch Application
#
################################################################################
'''

from __future__ import print_function
import argparse
import json
import os
import sqlite3
import sys


#### TODO
####  * Version the schema and put in checks


class CarDB(object):
    '''Object that encapsulates the Sqlite3 DB that contains data from a car,
    '''
    TYPE_MAP = {
        'integer': "INTEGER",
        'number': "REAL",
        'boolean': "INTEGER",
        'string': "TEXT"
    }

    def __init__(self, vin, dbFile, schema, create=True):
        ''' Instantiate a DB object for the car given by the VIN and connect to
            the given DB file.

            Inputs
                vin: VIN string for a car
                dbFile: Path to a Sqlite3 DB file (created if doesn't exist)
                schema: Dict containing the schema for all of the tables from
                    the Tesla API (that will become tables in the DB)
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

        self.schema = schema

        #### TODO validate schema version

        if 'tables' not in self.schema:
            raise Exception("'tables' field missing from schema")
        for tableName in self.schema['tables'].keys():
            cols = "id INTEGER PRIMARY KEY"
            keyList = self.schema['tables'][tableName]['properties'].keys()
            keyList.sort()
            for colName in keyList:
                colType = CarDB.TYPE_MAP[self.schema['tables'][tableName]['properties'][colName]['type']]
                cols += ", {0} {1}".format(colName, colType)
            self.createTable(tableName, cols)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        self.db.close()

    def createTable(self, tableName, tableCols):
        ''' Take name and the SQL column defintions for a Table and create it in
            the DB.

            Inputs
              tableName: String with name of table to be created
              tableCols: String with names and types of columns for table
        '''
        self.cursors[tableName] = None
        c = self.db.cursor()
        tableDef = "CREATE TABLE IF NOT EXISTS {0} ({1});".format(tableName, tableCols)
        c.execute(tableDef)
        self.db.commit()

    def getTable(self, tableName):
        '''Take name of table and return its rows in a dict.

            Inputs
              tableName: String with name of table to be created
        '''
        c = self.db.cursor()
        sqlCmd = "SELECT * FROM {0};".format(tableName)
        table = c.execute(sqlCmd).fetchall()
        return table

    def getTables(self):
        ''' Return contents of all tables in a dict, where keys are the names
            of the tables in the DB.

            Returns
              Dict with contents of all tables
        '''
        tables = {}
        for tableName in self.getTableNames():
            tables[tableName] = self.getTable(tableName)
        return tables

    def getTableNames(self):
        ''' Return list of table names in the current DB.

            Returns
              List of table names
        '''
        c = self.db.cursor()
        sqlCmd = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        r = c.execute(sqlCmd).fetchall()
        return (str(t[0]) for t in r)

    def insertRow(self, tableName, row):
        ''' Take name of table and a row of data and insert it into the table.

            Inputs
              tableName: String with name of table to be created
              row: dict whose keys are names of columns in the Table
        '''
        if not row:
            sys.stderr.write("WARNING: empty row for table '{0}'; skipping...\n".format(tableName))
            return
        c = self.db.cursor()
        cols = ", ".join('"{}"'.format(col) for col in row.keys())
        vals = ", ".join(':{}'.format(col) for col in row.keys())
        sqlCmd = 'INSERT INTO "{0}" ({1}) VALUES ({2})'.format(tableName, cols, vals)
        c.execute(sqlCmd, row)
        self.db.commit()

    def insertState(self, state):
        ''' Take dict with a row for each of one or more tables, and insert
            each of them into their table.

            Inputs
              state: A dict whose keys are the names of tables in the DB and whose
                     values are (single) rows for the given table.
        '''
        for tableName, row in state.iteritems():
            try:
                self.insertRow(tableName, row)
            except Exception as e:
                sys.stderr.write("WARNING: failed to log row to table {0}: {1}\n".format(tableName, e))

    def getRows(self, tableName):
        ''' Take name of table and return an iterator on the table's rows.

            Returns
              An iterator the returns one row of the table at a time, until no
              more exist, at which point it returns a None.
        '''
        self.cursors[tableName] = self.db.cursor()
        sqlCmd = "SELECT * FROM {0};".format(tableName)
        self.cursors[tableName].execute(sqlCmd)
        return self.cursors[tableName]


#
# TESTING
#
if __name__ == '__main__':
    DEF_SCHEMA_FILE = "./dbSchema.yml"

    DUMMY_VIN = "5YJSA1H10EFP00000"

    # Print the given message, print the usage string, and exit with an error.
    def fatalError(msg):
        ''' Print the given msg on stderr and exit.
        '''
        sys.stderr.write("Error: {0}\n".format(msg))
        sys.stderr.write("Usage: {0}\n".format(usage))
        sys.exit(1)

    usage = "Usage: {0} [-v] [-s <schemaFile>] <dbFile>"
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
