#!/usr/bin/env python

class ECMException(Exception):
	def __init__(self, message, obj):
		self.message = message
		self.obj = obj
	
		super(ECMException, self).__init__(message, obj)
		
		
'''Used when order status is not COM'''
class ECMOrderStatusError(Exception):
	pass

'''Used when ECM http status code of response is not 200'''
class ECMOrderResponseError(Exception):
	pass

'''Thrown when it's impossible to get a response from ECM'''
class ECMConnectionError(Exception):
	pass