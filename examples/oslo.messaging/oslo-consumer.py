#!/usr/bin/env python
# https://chrigl.de/posts/2014/08/27/oslo-messaging-example.html
# coding: utf-8

from oslo_config import cfg
import oslo_messaging as messaging
import logging

import eventlet
from test_config import *

class NotificationHandler(object):
    def info(self, ctxt, publisher_id, event_type, payload, metadata):
#        if publisher_id == 'testing':
        log.info('Handled')
        log.info('event_type: %s' % event_type)
        log.info('payload: %s' % payload)
        return messaging.NotificationResult.HANDLED

    def warn(self, ctxt, publisher_id, event_type, payload, metadata):
        log.info('WARN')

    def error(self, ctxt, publisher_id, event_type, payload, metadata):
        log.info('ERROR')

conf = cfg.ConfigOpts()
if __name__ == '__main__':
    eventlet.monkey_patch()

    logging.basicConfig()
    log = logging.getLogger()
    log.addHandler(logging.StreamHandler())
    log.setLevel(logging.INFO)

    log.info('Configuring connection')
    transport_url = ('rabbit://{username}:{password}@'
                     '{hostname}:{port}/'.format(**host_args))
    transport = messaging.get_transport(conf, transport_url)

    names = ['monitor', 'openstack']
    targets = [ messaging.Target(topic=n) for n in names ]
    endpoints = [NotificationHandler()]

    server = messaging.get_notification_listener(transport, targets, endpoints, allow_requeue=True, executor='eventlet')
    log.info('Starting up server')
    server.start()
    log.info('Waiting for something')
    server.wait()

# vim:ts=4:sw=4:et:shiftround:tw=79
