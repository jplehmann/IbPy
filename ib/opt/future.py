#!/usr/bin/env python
"""
Classes to simplify interactions with the ib.ext interface
for apps which don't need detailed asynchronous control.
Create futures directly or use the future factory.

NOTE: This API is unstable/beta and will possibly change!
"""
from time import sleep, time


class Future(object):
  """ Encapsulate IB callbacks and gather future responses.
  Provides blocking getters to retrieve responses received.
  A filter optionally limits the responses which are collected.
  
  Ideas for more methods:
  - sample (get the next after getter)
  - gather (gather N samples)

  The formulations can vary in how they:
  1. which message they retain (filter)
  2. update/clear the state of stored messages
  3. end or do not end the listening (autoclose)
  """
  def __init__(self, connection, timeout=5.0, minwait=0.1, sleeptime=0.1, autoclose=True) :
    """
    @param connection is the ib.opt.connection object
    @param timeout length of time to block for any reponse before throwing
    @param minwait minimum time to wait for responses after getter called, 
      to ensure that all responses have been received.
    @param autoclose whether to unregister listener after a getter is called
    """
    assert minwait < timeout, "Can't create future with timeout < minwait!"
    self.con = connection
    self.messages = []
    self.timeout = timeout
    self.minwait = minwait
    self.sleeptime = sleeptime
    self.autoclose = autoclose

  def notify(self, msg):
    """ Callback that delivers the message to the future.
    WARNING: this is called by another thread at times, thus any 
    operations here need to be thead safe!
    """
    if not self.filter(msg):
      return
    self.messages.append(msg)
    #print "Notified", self.name(), msg

  def get_first(self):
    return self.get(first_not_recent=True)

  def get_last(self):
    return self.get(first_not_recent=False)

  def get(self, first_not_recent=False):
    """ Retrieve a received notification.
    @param first_not_recent if True prefers the initial 
           notification over most recent.
    """
    return self._get_select(lambda x:x[0] if first_not_recent else x[-1])

  def get_all(self):
    """ Retrieve all received notifications.
    """
    return self._get_select(lambda x:x)

  def _get_select(self, select):
    """ Wait until we've received messages and we've waited the minimum 
    amount of time and return them, or we exceed the timeout duration.
    """
    startTime = time()
    elapsedTime = 0
    while not self.messages or elapsedTime < self.minwait:
      if elapsedTime > self.timeout:
        raise TimeoutException()
      sleep(self.sleeptime)
      elapsedTime = time() - startTime
    if self.autoclose:
      self.close()
    return select(self.messages)

  def close(self):
    """ Stop listening to events.
    """
    self.con.unregisterAll(self.notify)

  def name(self):
    """ Description of subclass.
    """
    raise NotImplementedError()

  def filter(self, msg):
    """ Select subset of notification messages to store.
    """
    return True


class FutureFactory:
  """ Factory to build and return a future.
  """
  def __init__(self, connection):
    self.con = connection

  def create(self, msgTypes, requestFct, *reqValues, **keyvalues):
    """ Create a future without a filter.
    """
    return self.create_filtered(msgTypes, None, requestFct, *reqValues, **keyvalues)

  def create_filtered(self, msgTypes, filter, requestFct, *reqValues, **keyvalues):
    """ Create a future with a filter.
    @param msgTypes one or more message types to register for
    @param requestFct the function on the connection to register with
    @param reqValues values to supply to request function
    """
    f = Future(self.con, **keyvalues)
    f.name = lambda : str(msgTypes)
    if filter:
      f.filter = filter
    for t in msgTypes if type(msgTypes) != str else [msgTypes]:
      self.con.register(f.notify, t)
    requestFct(*reqValues)
    return f


class TimeoutException(Exception):
    pass

