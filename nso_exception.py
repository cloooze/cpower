#!/usr/bin/env python


'''Thrown when it's impossible to get a response from NSO'''


class NSOConnectionError(Exception):
    pass

class VnfTypeException(Exception):
    pass
