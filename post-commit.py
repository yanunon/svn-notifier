#!/usr/bin/env python
#-*- coding:utf-8 -*-
'''
Created on 2012-03-18

@author: "Yang Junyong <yanunon@gmail.com>"
'''
import sys
import urllib2
import urllib
import os
PORT='8007'

if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit()
    project_path = sys.argv[1]
    project_rev = sys.argv[2]
    project_name = project_path[project_path.rfind('/')+1:]
    req_params = 'p=%s&r=%s&n=%s' % (project_path, project_rev, project_name)
    req_url = 'http://127.0.0.1:%s?%s' % (PORT, urllib.quote(req_params, ''))
    print req_url
    try:
        rsp = urllib2.urlopen(req_url)
        print rsp.read()
    except:
        print 'urlopen failed'
    
    sys.exit()
