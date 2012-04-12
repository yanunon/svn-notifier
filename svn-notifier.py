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
from ConfigParser import ConfigParser

# import for email
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.mime.text import MIMEText

# import for xmpp
from pyxmpp2.interfaces import EventHandler, event_handler, QUIT
from pyxmpp2.client import Client
from pyxmpp2.settings import XMPPSettings
from pyxmpp2.jid import JID
from pyxmpp2.streamevents import AuthorizedEvent, DisconnectedEvent
from pyxmpp2.message import Message


class GMail(object):
    
    def __init__(self, id, passwd):
        self.id = id
        self.passwd = passwd
        
    def send(self, receivers, subject, body):
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = self.id
        msg['To'] = ', '.join(receivers)
        txt = MIMEText(body)
        msg.attach(txt)
        
        try:
            smtp = smtplib.SMTP('smtp.gmail.com')
            smtp.starttls()
            smtp.login(self.id, self.passwd)
            smtp.sendmail(self.id, receivers, msg.as_string())
            smtp.quit()
        except Exception,e:
            print e
            print msg.as_string()
        

class MessageSender(Thread):
    def __init__(self, xmpp_client, email_client, queue, config, name='MessageSender'):
        Thread.__init__(self, name=name)
        self.xmpp_client = xmpp_client
        self.email_client = email_client
        self.queue = queue
        self.config = config
        self.is_run = True
        
    def run(self):
        while self.is_run:
            if self.queue.empty():
                time.sleep(0.1)
            else:
                msg = self.queue.get()
                receivers = self.config.get(msg['n'], 'receivers')
                receivers = receivers.split(',')
                msg_body = self.get_msg_body(msg)
                print msg_body
                if self.xmpp_client:
                    for receiver in receivers:
                        receiver_jid = JID(receiver.strip())
                        msg_obj = Message(to_jid=receiver_jid, body=msg_body, subject=None, stanza_type='chat')
                        try:
                            self.xmpp_client.stream.send(msg_obj)
                        except Exception, e:
                            print 'self.name Error%s' % e
                    print 'Send xmpp message'
                            
                if self.email_client:
                    subject = 'PRIS Project:[' + msg['n'] + '] SVN Updated'
                    self.email_client.send(receivers, subject, msg_body.encode('utf-8'))
                    print 'Send email message'
                
                
    def get_msg_body(self, msg):
        command = 'svn log file://%s -r%s' % (msg['p'], msg['r'])
        command = command.split(' ')
        p = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.wait()
        svn_log = p.stdout.read()
        svn_log = svn_log.split('\n')
        committer = svn_log[1].split('|')[1].strip()
        commit_msg = '\n'.join(svn_log[3:-2])
        msg_body = '[SVN Update]\nProject: %s\nVersion: %s\nCommitter: %s\nCommit Message:\n%s' % (msg['n'], msg['r'], committer, commit_msg)
        msg_body = msg_body.decode('utf-8')
        return msg_body
    
    def join(self, timeout=None):
        self.is_run = False
        Thread.join(self, timeout)

class GTalkRobot(EventHandler, Thread):
    
    def __init__(self):
        Thread.__init__(self, name='Robot')
        self.config = ConfigParser()
        self.use_xmpp = False
        self.use_email = False
        self.xmpp_client = None
        self.email_client = None
        
    def setup(self, config):
        self.config.read(config)
        self.use_xmpp = self.config.getboolean("Robot", 'xmpp')
        self.use_email =self.config.getboolean("Robot", 'email')
        self.sender_id = self.config.get("Robot", 'id')
        self.sender_passwd = self.config.get("Robot", 'passwd')
        
        if self.use_xmpp:
            self.xmpp_settings = XMPPSettings({'starttls': True, 'tls_verify_peer': False, 'password': self.sender_passwd})
            self.xmpp_client = Client(JID(self.sender_id), [self], self.xmpp_settings)
        
        if self.use_email:
            self.email_client = GMail(self.sender_id, self.sender_passwd)
            
        self.msg_queue = Queue()
        #self.receivers = [JID(receiver) for receiver in receivers]
        self.sender = MessageSender(self.xmpp_client, self.email_client, self.msg_queue, self.config)
        
        
    def run(self):
        if self.xmpp_client:
            self.xmpp_client.connect()
            self.xmpp_client.run()
        else:
            self.sender.start()

    def disconnect(self):
        if self.xmpp_client:
            self.xmpp_client.disconnect()
            self.xmpp_client.run(timeout = 2)
    
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
    
    def start(self):
        robot.setup(self.config)
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
    
