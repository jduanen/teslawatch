'''
################################################################################
#
# Geographic Features Library for TeslaWatch Application
#
################################################################################
'''

import sys
import time
import json
import random
import LatLon
import teslajson
from datetime import datetime
from optparse import OptionParser

'''
* Region Object encapsulates
  - coordinates that define a closed region
    * e.g., center and radius, polygon vertices
* Car Object encapsulates
  - state of car
    * States: Parked (Home/Work/Other), Moving, Stopped, Unknown
    * recent history of states
  - secrets/keys associated with car
  - event handler callback
  - Region objects
    * defined Home and Work regions
    * other regions of interest for the car
* Config file:
  - YAML
  - secret/protected file
  - read/updated by app
  - one or more cars
  - contents
    * user name
    * VIN
    * Tesla API id/secret
    * Regions (Home/Work/other)
    * messaging info
      - SMS: phone number, API key
'''

HOME_LAT = 37.460184
HOME_LON = -122.166203
HOME_LOC = LatLon.LatLon(LatLon.Latitude(HOME_LAT), LatLon.Longitude(HOME_LON))

WORK_LAT = 37.3848558
WORK_LON = -121.9947407
WORK_LOC = LatLon.LatLon(LatLon.Latitude(WORK_LAT), LatLon.Longitude(WORK_LON))

STANFORD_LAT = 37.430598
STANFORD_LON = -122.173109
STANFORD_LOC = LatLon.LatLon(LatLon.Latitude(STANFORD_LAT),
                             LatLon.Longitude(STANFORD_LON))


"""
DEG_TO_RAD = (math.pi / 180.0)
EARTH_RADIUS = ?

# Take a pair of lat/lon points and return the distance between them
#  in meters.
def distance(lat1, lon1, lat2, lon2):
    # phi = 90 - latitude
    phi1 = (90.0 - lat1) * DEG_TO_RAD
    phi2 = (90.0 - lat2) * DEG_TO_RAD

    # theta = longitude
    theta1 = lon1 * DEG_TO_RAD
    theta2 = lon2 * DEG_TO_RAD

    # compute spherical distance from spherical coordinates
    # For two locations in spherical coordinates: (1, theta, phi) and
    #  (1, theta', phi'), cosine( arc length ) =
    #    sin phi sin phi' cos(theta-theta') + cos phi cos phi'
    # distance = rho * arc length
    cos = (math.sin(phi1) * math.sin(phi2) * math.cos(theta1 - theta2) +
           math.cos(phi1) * math.cos(phi2))
    arc = math.acos(cos)

    # multiply arc by the radius of the earth in meters to get distance
    return arc * EARTH_RADIUS
"""

# Base class for shapes that define geographic regions of interest.
#### TODO consider using abc to define the abstract base class's methods
#### For now, must provide the following methods:
####  * getDistance(lat, lon) -- returns distance to closest edge in Km (float)
####  * isInside(lat, lon) -- returns True if given point is inside
class Shape(object):
    def __init__(self, id=None):
        if id is None:
            self.id = str(int(random.random() * 100000))
        else:
            self.id = id


# This object defines a circle of a given radius around a point (given my a
#  latitude and longitude pair).
# If no 'id' is given, a random one will be chosen.
# Can get a distance from some coordinates to the center of this point, or to
#  the edge of the circle.
# Can also ask if a given location is inside the circle or not.
# The 'radius' arg is Km (float), and 'id' is a string (or a random number is
#  generated if none is given).
class Circle(Shape):
    def __init__(self, lat, lon, radius, id=None):
        super(Circle, self).__init__(id)
        self.location = LatLon.LatLon(LatLon.Latitude(lat),
                                      LatLon.Longitude(lon))
        self.radius = radius

    def _getDistance(self, lat, lon):
        d = self.location.distance(LatLon.LatLon(LatLon.Latitude(lat),
                                                 LatLon.Longitude(lon)))
        return d

    def isInside(self, lat, lon):
        d = self._getDistance(lat, lon)
        if d < self.radius:
            return True
        else:
            return False

# Take a lat/lon pair and a polygon (defined by a list of lat/lon tuples),
#  and return True if the point is inside the polygon.
def isInsidePolygon(lat, lon, poly):
    n = len(poly)
    inside = False

    p1Lat, p1Lon = poly[0]
    for i in range(n + 1):
        p2Lat, p2Lon = poly[i % n]
        if lon > min(p1Lon, p2Lon):
            if lon <= max(p1Lon, p2Lon):
                if lat <= max(p1Lat, p2Lat):
                    if p1Lon != p2Lon:
                        latIntrs = (lon - p1Lon) * (p2Lat - p1Lat) / (p2Lon - p1Lon) + p1Lat
                    if p1Lat == p2Lat or lat <= latIntrs:
                        inside = not inside
        p1Lat, p1Lon = p2Lat, p2Lon
    return inside


# This object defines a polygon (given by a set of latitude and longitude
#  tuples representing verticies).
class Polygon(Shape):
    def __init__(self, poly, id=None):
        super(Polygon, self).__init__(id)
        self.poly = poly

    def isInside(self, lat, lon):
        return isInsidePolygon(lat, lon, self.poly)


# This object defines a rectangle (given by a pair of latitude and longitude
#  pairs representing a set of diagonal corners).
class Rectangle(Polygon):
    def __init__(self, lat1, lon1, lat2, lon2, id=None):
        minLat = min(lat1, lat2)
        maxLat = max(lat1, lat2)
        minLon = min(lon1, lon2)
        maxLon = max(lon1, lon2)
        poly = [(minLat, maxLon), (minLat, minLon),
                (maxLat, minLon), (maxLat, maxLon)]
        super(Rectangle, self).__init__(poly, id)


# This object takes a circle and makes a geofence out of it.
# ????
# do things like delete when departs, keep track of entry and exit times,
#  keep track of last point
class Fence(Shape):
    def __init__(self, shape, onEnter=None, onExit=None):
        self.shape = shape
        self.onEnter = onEnter
        self.onExit = onExit
        self.lat = self.lon = None
        self.lastUpdated = None
        self.inside = None
        self.enterTime = self.exitTime = None

    def update(self, lat, lon, time):
        self.lat = lat
        self.lon = lon
        self.time = time
        now = datetime.now()
        self.lastUpdated = now
        inside = self.shape.isInside(lat, lon)
        if self.inside is None:
            self.inside = inside
        else:
            if self.inside != inside:
                # got a state transition
                if inside:
                    # wasn't inside, and now it is
                    self.enterTime = now
                    callback = self.onEnter
                else:
                    # was inside, and now it isn't
                    self.exitTime = now
                    callback = self.onExit
                # ????


class Region(object):
    '''
        Inputs
          specs: dict of Region Specifications
    '''
    def __init__(self, specs):
        pass

    def isInRegion(self, location):
        ''' Take a location object and return True if it is in the Region.
            Inputs
              location: a Location object

            Returns
              True if location within the Region, or False if not
        '''
        pass


#
# TESTING
#
if __name__ == '__main__':
    usage = "Usage: {0} [-v] [-u <email>] -p <pswd> [-V <vin>]"
    parser = OptionParser(usage)
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                      default=False, help="print debug info")
    parser.add_option("-u", "--user", action="store", type="string",
                      dest="user", default=DEF_USER, help="user email address")
    parser.add_option("-p", "--password", action="store", type="string",
                      dest="password", default=None, help="user password")
    parser.add_option("-V", "--VIN", action="store", type="string",
                      dest="vin", help="Vehicle Id Number")
    (options, args) = parser.parse_args()

    # initialize and validate inputs
    if options.password is None:
        sys.stderr.write("Error: must provide password\n")
        sys.exit(1)

    # pre-execution printouts
    if options.verbose:
        sys.stdout.write("    User: {0}\n".format(user))
        if options.vin:
            sys.stdout.write("    VIN:  {0}\n".format(vin))
