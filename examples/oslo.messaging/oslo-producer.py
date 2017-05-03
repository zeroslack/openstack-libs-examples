#!/usr/bin/env python
# https://chrigl.de/posts/2014/08/27/oslo-messaging-example.html

# coding: utf-8
from __future__ import print_function
from oslo_config import cfg
import oslo_messaging as messaging
import logging
import sys

if __name__ == '__main__':
    logging.basicConfig()
    log = logging.getLogger()

#log.addHandler(logging.StreamHandler())
    log.setLevel(logging.INFO)

    conf = cfg.ConfigOpts()
    conf(sys.argv[1:])
    conf.log_opt_values(log, logging.INFO)

    # TODO(zeroslack): get from mulit-value configopt
    host_args = {
        'hostname': '10.0.100.11',
        'port': 5672,
        'username': 'guest',
        'password': 'oAhY0TfFvFktUPbBs29v'
    }

    transport_host = messaging.TransportHost(**host_args)
    transport_url = messaging.TransportURL(conf,
                                           hosts=[transport_host],
                                           transport='rabbit')
#    transport_url = ('rabbit://{username}:{password}@'
#                     '{hostname}:{port}/'.format(**host_args))
    transport = messaging.get_transport(conf, transport_url)
    driver = 'messaging'
    notifier = messaging.Notifier(transport,
                                  driver=driver,
                                  publisher_id='testing')

    notifier.info({'some': 'context'}, 'just.testing', {'heavy': 'payload'})

# vim:ts=4:sw=4:et:shiftround:tw=79
