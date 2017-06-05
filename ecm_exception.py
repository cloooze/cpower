#!/usr/bin/env python


class ECMException(Exception):
    def __init__(self, message, obj):
        self.message = message
        self.obj = obj

        super(ECMException, self).__init__(message, obj)


class ECMConnectionError(Exception):
    """There was (any) connection error while handling the request. """
    pass

