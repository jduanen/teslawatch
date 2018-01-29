'''
################################################################################
#
# Notifier Object for TeslaWatch Application
#
################################################################################
'''

import json
import os
import sys

from tracker import EVENT_TYPES


# path to notifier programs
NOTIFIER_DIR = "./notifiers"


class Notifier(object):
    ''' Per-car object that can encapsulates the events and (external) programs
        that re used to generate notifications for each type of event.
    '''
    def __init__(self, notifiers):
        self.notifiers = {}
        for notifier, eventTypes in notifiers.iteritems():
            fPath = os.path.join(NOTIFIER_DIR, notifier)
            if not os.path.isfile(fPath) or not os.access(fPath, os.X_OK):
                raise ValueError("Invalid notifier program '{0}' for events '{1}".
                                 format(fPath, eventTypes))
            if not set(eventTypes).issubset(set(EVENT_TYPES)):
                raise ValueError("Invalid event types '{0}' for notifier '{1}'".
                                 format(set(eventTypes) - set(EVENT_TYPES), notifier))
            for eventType in eventTypes:
                if eventType not in self.notifiers:
                    self.notifiers[eventType] = []
                self.notifiers[eventType].append(fPath)

    def __str__(self):
        s = "eventsNotifiers: "
        j = json.dumps(self.notifiers, indent=4, sort_keys=True)
        return s + j

    def notify(self, eventType, arg=None):
        if not arg:
            raise ValueError("Must provide arg")
        for notifier in self.notifiers[eventType]:
            #### FIXME call all the notifiers (with the given arg) that ar associated with this event type
            print("Event: {0}, Notifier: {1}({2})".format(eventType, notifier, arg))
            if os.system("{0} {1}".format(notifier, arg)):
                raise Exception("Command '{0}({1})' failed")


#
# TESTING
#
if __name__ == '__main__':
    TEST_NOTIFIERS = {
        'sms.py': [
            "STOPPED_MOVING",
            "STARTED_MOVING"
        ],
        'testScript.sh': [
            "ENTER_REGION"
        ]
    }

    # should work
    try:
        n = Notifier(TEST_NOTIFIERS)
        print(n)

        n.notify("STOPPED_MOVING", "xxx")

        n.notify("ENTER_REGION", "yyy")
    except Exception as e:
        print("FAILED: {0}".format(e))
        sys.exit(1)

    # should fail
    err = False
    try:
        n.notify("ENTER_REGION")
    except Exception:
        err = True
    if not err:
        print("FAILED: to fail")
        sys.exit(1)

    # should fail
    err = False
    try:
        n = Notifier({'asdf': ["EXIT_REGION"]})
        n.notify("EXIT_REGION")
    except Exception:
        err = True
    if not err:
        print("FAILED: to fail")
        sys.exit(1)

    # should fail
    err = False
    try:
        n = Notifier({'sms.py': ["XYZZY"]})
        n.notify("XYZZY")
    except Exception:
        err = True
    if not err:
        print("FAILED: to fail")
        sys.exit(1)

    print("SUCCEEDED")
