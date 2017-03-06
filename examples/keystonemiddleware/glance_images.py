#!/usr/bin/env python

# http://www.jamielennox.net/blog/2015/09/10/user-auth-in-openstack-services
from glanceclient import client
import json
from keystoneclient import session
from keystonemiddleware import auth_token
from oslo_config import cfg
import webob.dec
from wsgiref import simple_server


# TODO: --help doesn't seem to work either way...
cfg.CONF(project='testservice')
session.Session.register_conf_options(cfg.CONF, 'communication')
SESSION = session.Session.load_from_conf_options(cfg.CONF, 'communication')

@webob.dec.wsgify
def app(req):
    glance = client.Client('2',
                           session=SESSION,
                           auth=req.environ['keystone.token_auth'])

    return webob.Response(json.dumps([i.name for i in glance.images.list()]))


app = auth_token.AuthProtocol(app, {})
server = simple_server.make_server('', 8000, app)
#server.serve_forever()

if __name__ == '__main__':
    import logging
    import sys
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    logger = logging.getLogger(cfg.CONF.project)
    cfg.CONF.log_opt_values(cfg.LOG, cfg.logging.INFO)
    server.serve_forever()
