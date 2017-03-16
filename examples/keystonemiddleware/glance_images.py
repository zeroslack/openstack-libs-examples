#!/usr/bin/env python

# http://www.jamielennox.net/blog/2015/09/10/user-auth-in-openstack-services
from glanceclient import client
import json
from keystoneclient import session
from keystoneclient import client as ks_client
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
# N.B. below does not work
# 
# DiscoveryFailure: Not enough information to determine URL. Provide either a Session, or auth_url or endpoint
#    kclient = ks_client.Client('3',
#                               session=SESSION,
#                               auth=req.environ['keystone.token_auth'])

# TODO(kamidzi): Need to handle InvalidToken exception
    glance = client.Client('2',
                           session=SESSION,
                           auth=req.environ['keystone.token_auth'])

    resp = {
        'glance_images': [i.name for i in glance.images.list()],
        'keystone.token_auth.user': req.environ['keystone.token_auth'].user._data,
    }

    return webob.Response(json.dumps(resp))

if __name__ == '__main__':
    import logging
    import sys
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    logger = logging.getLogger(cfg.CONF.project)

    app = auth_token.AuthProtocol(app,{})
    server = simple_server.make_server('', 8000, app)
    server.serve_forever()
