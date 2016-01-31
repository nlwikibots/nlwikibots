####################################################
# $Id: querier.py 1 2006-12-24 19:58:34Z valhallasw $
####################################################
# MySQLdb command abstraction layer
# (C)2006 by Merlijn 'valhallasw' van Deen [valhallasw at arctus dot nl]
#
# Licenced under the MIT license
# http://www.opensource.org/licenses/mit-license.php
####################################################
# Usage:
# ------
# import querier
# var = querier.querier(host="localhost", etc) #same as MySQLdb.connect attributes
# result = var.do("MySQL query")               #same as cursor.execute attributes
#
# all other functions are made purely for use on mediawiki tables.
#
# The result is a list of dictionaries: [{'colname': data1, 'colname2': data2},{'colname': data11, 'colname2': data22}]
####################################################

import MySQLdb, MySQLdb.cursors

# classes

class querier:
  def __init__(self,*args,**kwargs):
    
    self.counter = 0
    self.verbose = kwargs.pop('verbose', False) # if key 'verbose' is True, self.verbose = True, else False.
      
    if 'read_default_file' not in kwargs:
        kwargs['read_default_file'] = '~/replica.my.cnf' #read toolserver database information (please make sure the host is listed in the file)

    kwargs['cursorclass'] = MySQLdb.cursors.DictCursor
    self.db = MySQLdb.connect(*args,**kwargs)
    self.lastrowid = None
  
  def do(self, *args,**kwargs):
    transpose = kwargs.pop('transpose', False)
    mediawiki = kwargs.pop('mediawiki', False)
    if self.verbose:
       print args
    
    cursor = self.db.cursor()
    cursor.execute(*args,**kwargs)
    retval = tuple(cursor.fetchall())
    #erwin85 edit: lastrowid
    self.lastrowid = cursor.lastrowid
    cursor.close()
    self.counter = self.counter + 1

    if mediawiki:
      retval = map(self.doutf8, retval)

    if transpose:
      if len(retval) > 0:
        return dict(zip(retval[0].keys(),zip(*map(dict.values,retval))))
        # 17:36 < dodek> valhalla1w, you're posting it on obfuscated python coding contest or sth? :)
	# 17:36 < valhalla1w> actually i'm trying to transpose a list of dicts to a dict of lists
	# 17:42 < valhalla1w> s/list/tuple
      else:
        return {}

    return retval

  def doutf8(self, dictitem):
    for (name, item) in dictitem.iteritems():
      if isinstance(item, str):
        dictitem.update(dict([[name, item.decode('utf8')]]))

    return dictitem
