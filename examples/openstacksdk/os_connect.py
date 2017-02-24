#!/usr/bin/env python
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

# Fix this...
from __future__ import print_function
import os.path
d = os.path.dirname(__file__)
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.join(d, '../'))))

#import auth_types
from auth_types import AuthSwitcher
from auth_types import cfg
import logging
import os
import os_client_config

from openstack import connection
from openstack import profile
from openstack import utils



class Opts(object):
    def __init__(self, cloud_name='test_cloud', debug=False):
        self.cloud = cloud_name
        self.debug = debug
        # Use identity v3 API for examples.
        self.identity_api_version = '3'


def _get_resource_value(resource_key, default):
    try:
        return cloud.config['example'][resource_key]
    except KeyError:
        return default


#SERVER_NAME = 'openstacksdk-example'
#IMAGE_NAME = _get_resource_value('image_name', 'cirros-0.3.5-x86_64-disk')
#FLAVOR_NAME = _get_resource_value('flavor_name', 'm1.small')
#NETWORK_NAME = _get_resource_value('network_name', 'private')
#KEYPAIR_NAME = _get_resource_value('keypair_name', 'openstacksdk-example')
#SSH_DIR = _get_resource_value(
#    'ssh_dir', '{home}/.ssh'.format(home=os.path.expanduser("~")))
#PRIVATE_KEYPAIR_FILE = _get_resource_value(
#    'private_keypair_file', '{ssh_dir}/id_rsa.{key}'.format(
#        ssh_dir=SSH_DIR, key=KEYPAIR_NAME))
#
#EXAMPLE_IMAGE_NAME = 'openstacksdk-example-public-image'
#

def create_connection_from_config():
    opts = Opts(cloud_name=TEST_CLOUD)
    occ = os_client_config.OpenStackConfig()
    cloud = occ.get_one_cloud(opts.cloud)
    return connection.from_config(cloud_config=cloud, options=opts)


def create_connection_from_args():
    parser = argparse.ArgumentParser()
    config = os_client_config.OpenStackConfig()
    config.register_argparse_arguments(parser, sys.argv[1:])
    args = parser.parse_args()
    return connection.from_config(options=args)


def create_connection(**kwargs):
    prof = profile.Profile()
    region = kwargs.get('region', None)
    prof.set_region(profile.Profile.ALL, region)

    return connection.Connection(
        profile=prof,
        user_agent='examples',
        auth_url=kwargs.pop('auth_url'),
        project_name=kwargs.pop('project_name'),
        username=kwargs.pop('username'),
        password=kwargs.pop('password')
    )

class SdkAuthSwitcher(AuthSwitcher):
    @property
    def auth_url(self):
        # TODO - use discovered urls
        conf = self.conf
        if conf.auth_url:
            return conf.auth_url
        else:
            return conf.os_service_endpoint ('/v%s' % conf.os_identity_api_version)

if __name__ == '__main__':
    utils.enable_logging(True, stream=sys.stdout)

    try:
        auth_switcher = SdkAuthSwitcher()
        auth_switcher.configure(sys.argv[1:])
    except (cfg.Error) as e:
        sys.exit(e)
    logger = auth_switcher.logger 
    conf = auth_switcher.conf
    conf.log_opt_values(logger=logger, lvl=logging.INFO)

    TEST_CLOUD = 'example'
    occ_kwargs = {
    #    'config_files': ['clouds.yaml']
    }
    occ = os_client_config.OpenStackConfig(**occ_kwargs)
    cloud = occ.get_one_cloud(TEST_CLOUD)
    REGION = None
    conn_kwargs = {
        # Note that sending versioned urls seem to require additional params
        # By default it appears v2.0 is used?
        'auth_url': auth_switcher.os_service_endpoint,
        'region': REGION,
        'project_name': conf.project_name,
        'username': conf.username,
        'password': conf.password
    }

    conn = create_connection(**conn_kwargs)
    projects = list(conn.identity.projects())
    print(projects)

# vim:ts=4:sw=4:shiftround:et:
