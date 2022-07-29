# teslawatch -- DEPRECATED
Tesla tracker with geofencing and SMS notifications -- DEPRECATED

**This is work-in-progress and currently non-functional.**

This depends on the 'teslajson' package from: `https://github.com/gglockner/teslajson`

Needs a configuration file that defines ????
  it's a private file, so protect it properly (TODO do the check)
  it's read and updated by the script
    - this is where regions are stored

Regions
  built-in notions of "HOME" and "WORK", the rest are user-defined
  different shapes possible -- circle, polygon
  define in different ways:
    coordinates, relative to current location, map input (TODO)
  delete/modify via ????

States
  Parked (Home, Work, Region, Other)
  Moving
  Stopped

Events
  state transitions
    can choose different notifications for each event
  geofences: enter/leave

Notifications
  callbacks
  different types
    email
    SMS
    log to file

TODO:
  * Geofence -- notify when arriving/departing locations (e.g., home)
  * notify on state transitions (was moving and now stopped, vice versa)
  * monitor temp and turn on a/c if too hot
  * look at weather and make sure roof is closed if raining
  * update more frequently when moving
  * notify if within X distance of current location
  * rewrite all of this
  * use multiple instances or multiprocessing to handle multiple cars
  * focus on state transitions: states=[parked, moving], events=[parked->moving, moving->parked]
  * different polling intervals for different states -- e.g., parked@home, nighttime, moving, etc.
  * use different packages to send SMS notifications
    - textbelt
    - google hangouts: "hangups" package python3
  * make notification backend be pluggable
  * rewrite to be Python3
  * fix up the cmd-line interface
  * build mapping front-end to define/display geofences
  * make basic features work without geofencing
  * define config file format
  * keep textbelt key secret too


DESIGN NOTES:
* Array of cars objects
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
  - process:
    * read from file
    * match up VIN numbers with those returned from Tesla API
    * instantiate car object for each match
    * (optionally) whine about mismatches (on either side)
