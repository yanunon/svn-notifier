#!/usr/bin/env python
#-*- coding:utf-8 -*-
'''
Created on 2012-03-18

@author: "Yang Junyong <yanunon@gmail.com>"
'''

import pyxmpp2
import BaseHTTPServer
import SocketServer
import os
import sys
import time
import urllib, urllib2
import subprocess

from threading import Thread
from Queue import Queue


from pyxmpp2.interfaces import EventHandler, event_handler, QUIT
from pyxmpp2.client import Client
from pyxmpp2.settings import XMPPSettings
from pyxmpp2.jid import JID
from pyxmpp2.streamevents import AuthorizedEvent, DisconnectedEvent
from pyxmpp2.message import Message



class MessageSender(Thread):
    def __init__(self, client, queue, receivers, name='MessageSender'):
        Thread.__init__(self, name=name)
        self.client = client
        self.queue = queue
        self.receivers = receivers
        self.is_run = True
        
    def run(self):
        while self.is_run:
            if self.queue.empty():
                time.sleep(0.1)
            else:
                msg = self.queue.get()
                msg_body = self.get_msg_body(msg)
                print msg_body
                for receiver in self.receivers:
                    msg_obj = Message(to_jid=receiver, body=msg_body, subject=None, stanza_type='chat')
                    try:
                        self.client.stream.send(msg_obj)
                    except Exception, e:
                        print 'self.name Error%s' % e
                print 'Send msg'
                
    def get_msg_body(self, msg):
        command = 'svn log file://%s -r%s' % (msg['p'], msg['r'])
        command = command.split(' ')
        p = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.wait()
        svn_log = p.stdout.read()
        svn_log = svn_log.split('\n')
        committer = svn_log[1].split('|')[1].strip()
        commit_msg = svn_log[3]
        msg_body = '[SVN Update]\nProject: %s\nVersion: %s\nCommitter: %s\nCommit Message: %s' % (msg['n'], msg['r'], committer, commit_msg)
        msg_body = msg_body.decode('utf-8')
        return msg_body
    
    def join(self, timeout=None):
        self.is_run = False
        Thread.join(self, timeout)

class GTalkRobot(EventHandler, Thread):
    
    def __init__(self):
        Thread.__init__(self, name='GTalkRobot')
        
        
    def setup(self, id, passwd, receivers):
        self.settings = XMPPSettings({'starttls': True, 'tls_verify_peer': False, 'password': passwd})
        self.client = Client(JID(id), [self], self.settings)
        self.msg_queue = Queue()
        self.receivers = [JID(receiver) for receiver in receivers]
        self.sender = MessageSender(self.client, self.msg_queue, self.receivers)
        
    def run(self):
        self.client.connect()
        self.client.run()

    def disconnect(self):
        self.client.disconnect()
        self.client.run(timeout = 2)
    
    def join(self, timeout=None):
        self.disconnect()
        Thread.join(self, timeout)
    
    
    def add_msg(self, msg):
        self.msg_queue.put(msg)
    
    @event_handler(AuthorizedEvent)
    def handle_authorized(self, event):
        self.sender.start()
    
    @event_handler(DisconnectedEvent)
    def handle_disconnected(self, event):
        self.sender.join()
        return QUIT
    
robot = GTalkRobot()

class NetHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    global robot
    def do_GET(self):
        self.send_response(200, 'Got it!')
        
        parsed_path = urllib2.urlparse.urlparse(self.path)
        if parsed_path.path == '/':
            query = urllib.unquote(parsed_path.query)
            params = dict([part.split('=') for part in query.split('&')])
            robot.add_msg(params)

class NetServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    pass

        
class Notifier(object):
    global robot
    def __init__(self, config='.config', port=8007):
        self.config = config
        self.port = port

        if os.path.exists(self.config):
            f = open(self.config, 'r')
            self.emails = [line[:-1].strip() for line in f.readlines()]
            f.close()
    
    def start(self):
        robot.setup('sender_id', 'sender_passwd', self.emails)
        robot.start()
        
        self.httpd = NetServer(('', self.port), NetHandler)
        self.httpd.serve_forever()
        
    def stop(self):
        robot.join()
        self.httpd.shutdown()

if __name__ == '__main__':
    notifier = Notifier()
    
    try:
        notifier.start()
    except KeyboardInterrupt:
        pass
    notifier.stop()
    
