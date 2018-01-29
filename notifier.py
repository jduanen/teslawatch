'''
################################################################################
#
# Notifier Object for TeslaWatch Application
#
################################################################################
'''

import os

from tracker import EVENT_TYPES


# path to notifier programs
NOTIFIER_DIR = "."


class Notifier(object):
    ''' Per-car object that can encapsulates the events and (external) programs
        that re used to generate notifications for each type of event.
    '''
    def __init__(self, eventNotifiers):
        eventTypes = eventNotifiers.keys()
        if not set(eventTypes).issubset(set(EVENT_TYPES)):
            raise ValueError("Invalid event types: {0}".format(set(eventTypes) - set(EVENT_TYPES)))

        for eventType, notifier in eventNotifiers.iteritems():
            fPath = os.path.join(NOTIFIER_DIR, notifier)
            if not notifier or not os.path.isfile(fPath) or not os.access(fPath, os.X_OK):
                raise ValueError("Invalid notifier program '{0}' for event '{1}".format(fPath, eventType))
        self.eventNotifiers = eventNotifiers

    def __str__(self):
        return "Events/Notifiers: {0}".format(self.eventNotifiers)

    def notify(self, eventType, arg):
        #### FIXME
        print("Event: {0}, Notifier: {1}({2})".format(eventType, self.eventNotifiers[eventType], arg))


#
# TESTING
#
if __name__ == '__main__':
    #### TODO implement test cases
    pass
