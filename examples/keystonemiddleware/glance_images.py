#!/usr/bin/env python

# http://www.jamielennox.net/blog/2015/09/10/user-auth-in-openstack-services
from glanceclient import client
import json
from keystoneclient import session
from keystonemiddleware import auth_token
from oslo_config import cfg
import webob.dec
from wsgiref import simple_server
import os
import sys

CONF = cfg.CONF
CONF(project='testservice')
session.Session.register_conf_options(cfg.CONF, 'communication')
vars = filter(lambda x: x[0].startswith('OS_'), os.environ.iteritems())
conf_keys = CONF.keys()
for k, v in vars:
# Try the full var first
    n = k.lower()
    cands = (n, n[3:])
    for var in cands:
        if var in conf_keys:
            self.conf.set_default(name=var, default=v)
            break

CONF(sys.argv[1:])

# TODO: --help doesn't seem to work either way...
SESSION = session.Session.load_from_conf_options(cfg.CONF, 'communication')

@webob.dec.wsgify
def app(req):
    print(Exception(req.environ['keystone.token_auth']._auth.__dict__))
    glance = client.Client('2',
                           session=SESSION,
                           auth=req.environ['keystone.token_auth'])

    return webob.Response(json.dumps([i.name for i in glance.images.list()]))

if __name__ == '__main__':
    import logging
    import sys
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    logger = logging.getLogger(cfg.CONF.project)

    app = auth_token.AuthProtocol(app,{})
    server = simple_server.make_server('', 8000, app)
    server.serve_forever()
