#!/usr/bin/env python
from __future__ import print_function
try:
    from keystoneauth1.identity import v2 as authv2, v3 as authv3
    from keystoneauth1 import loading
    from keystoneauth1 import session as auth_session
    from keystoneauth1 import discover as kauth_discover
    HAS_KEYSTONEAUTH1 = True
except ImportError as ex:
    from sys import stderr
    print(ex.message, file=stderr)
    HAS_KEYSTONEAUTH1 = False
from keystoneclient.auth.identity import v2, v3
from keystoneclient import discover as ks_discover
from keystoneclient import session as legacy_session
from oslo_config import cfg
from re import sub
from urllib3.util import parse_url
from urllib3.util.url import Url
import keystoneclient
import logging
import os
import pbr.version
import sys


class AuthSwitcher(object):
    CONF_FILE = '.authswitch.conf'
    DEFAULT_API_VERSION = '3'

    def __init__(self, os_service_endpoint=None):
        self._conf = self._configure_options()
        self._ks_client = None
        self.os_service_endpoint = os_service_endpoint
        # initial logger
        self._logger = self._get_logger()

    @property
    def logger(self):
        return self._logger

    def _get_logger(self):
        # import importlib
        # importlib.import_module('logging')
        self._logging_handlers = {}
        log = logging.getLogger(self.__module__)
        ch = logging.StreamHandler(stream=sys.stdout)
        ch.setLevel(logging.INFO)
        # This is suspect...
        log.addHandler(ch)
        self._logging_handlers['info'] = ch
        log.setLevel(logging.INFO)
        return log

    def configure(self, *args, **kwargs):
        vars = filter(lambda x: x[0].startswith('OS_'), os.environ.iteritems())
        conf_keys = self.conf.keys()
        for k, v in vars:
        # Try the full var first
            n = k.lower()
            cands = (n, n[3:])
            for var in cands:
                if var in conf_keys:
                    self.conf.set_default(name=var, default=v)
                    break

        self.conf(args[0])

        # bail using keystoneauth1 if not available.
        # FIXME: this is hacky...
        if self.conf.use_keystoneauth1 and not HAS_KEYSTONEAUTH1:
            raise Exception('Requested module keystoneauth1 is not available.')
        # adjust the logging
        if self.conf.debug:
            ch = logging.StreamHandler(stream=sys.stderr)
            ch.setLevel(logging.DEBUG)
            self.logger.addHandler(ch)
            # This is questionable...
            self._logging_handlers['debug'] = ch
            self.logger.removeHandler(self._logging_handlers['info'])
            self.logger.setLevel(logging.DEBUG)

        self.os_service_endpoint = self.conf.os_service_endpoint
        if self.os_service_endpoint is None:
            base = {'path': None}
            url = parse_url(self.conf.auth_url)
            l = list(url)[:4] + [None]*(len(url._fields)-4)
            self.os_service_endpoint = Url(*l).url
            self.conf.set_default('os_service_endpoint',
                                  default=self.os_service_endpoint)

    def _configure_options(self):
        """Configure options. Options take precedence in the following order:
         - command-line options
         - configuration file (sic)
         - environmental variables
        """
        CONF_FILE = self.CONF_FILE
        _conf = cfg.ConfigOpts()

        # Hack alert...
        # TODO: maybe this should be a map in future..
        min_semver = (3, 15, 0)
        verinfo = pbr.version.VersionInfo('oslo.config')
        oslo_cfg_semver = verinfo.semantic_version().version_tuple()[:3]

        nsd_opt_args = {
            'help': ('Use null-sessions in version discovey.'
                    'This shouldn\'t be a gloabl opt.'),
            'default': False,
        }
        if oslo_cfg_semver >= min_semver:
             nsd_opt_args['advanced'] = True

        cli_global_opts = [
            cfg.BoolOpt('debug',
                        help='Enable debug logging',
                        default=False),
            cfg.BoolOpt('null-session-discovery',
                        **nsd_opt_args),
            cfg.BoolOpt('use-keystoneauth1',
                        help='Use keystoneuth1',
                        default=True),
            cfg.StrOpt('os-service-endpoint',
                       required=True,
                       help='Base url for authentication'),
            cfg.StrOpt('os-identity-api-version',
                       # TODO: this is suspect... see AuthSwitcher#configure()
                       default=os.environ.get('OS_IDENTITY_API_VERSION',
                                              self.DEFAULT_API_VERSION),
                       choices=['2.0', '3']),
        ]

        opt_map = {
            'keystoneclient': {
                'group': cfg.OptGroup(name='keystoneclient',
                                      title='Keystone Options'),
                'options': [
                    {
                        'opt': cfg.BoolOpt('use-sessions',
                                           help='Use (deprecated)'
                                                ' keystone sessions',
                                           default=True),
                        'cli': True
                    },
                    {
                        'opt': cfg.BoolOpt('use-discovery',
                                           help='Use service discovery',
                                           default=False),
                        'cli': True
                    }
                ],

            },
            'keystoneauth1': {
                'group': cfg.OptGroup(name='keystoneauth1',
                                      title='keystoneauth1 Options'),
                'options': [
                    {
                        'opt': cfg.BoolOpt('use-sessions',
                                           help='Use keystoneauth1 sessions',
                                           default=True),
                        'cli': True
                    },
                    {
                        'opt': cfg.BoolOpt('use-discovery',
                                           help='Use service discovery',
                                           default=True),
                        'cli': True
                    },
                    {
                        'opt': cfg.BoolOpt('use-loading',
                                           help='Use keystoneauth1 plugin '
                                                'loading interface',
                                           default=True),
                        'cli': True
                    }
                ]

            }

        }

        # Following is a bit suspect...
        # It is not known what the session module will be at this point
        # cli_global_opts += legacy_session.Session.get_conf_options()
        # cli_global_opts += keystoneclient.auth.get_common_conf_options()
        for groupname, attrs in opt_map.iteritems():
            if 'group' in attrs:
                group = attrs['group']
                _conf.register_group(group)
            else:
                # Fallback to group name
                group = groupname
            for optdesc in attrs.get('options', []):
                kwargs = {'group': group}
                kwargs.update(optdesc)
                _conf.register_opt(**kwargs)

        # Assume here that we'll be using passwords
        required_opts = ('password', 'username', 'project_name')
        auth_opts = keystoneclient.auth.get_plugin_options('password')

        def set_required(opt):
            if opt.dest not in required_opts:
                return opt
            opt.required = True
            return opt

        cli_global_opts += map(set_required, auth_opts)
        # This is done serially to make cli/config versions behave together
        # (otherwise auto-scoping by OptionGroup seems to malfunction)
        for opt in cli_global_opts:
            _conf.register_opt(opt, cli=True)

        if os.path.exists(CONF_FILE) and os.access(CONF_FILE, os.R_OK):
            _conf(default_config_files=[CONF_FILE])

        return _conf

    @property
    def conf(self):
        return self._conf

    def _get_auth_args(self, version=None, **kwargs):
        auth_args = {
            'username': self.conf.username,
            'password': self.conf.password,
        }

        if version is None:
            # FIXME: is this always set?
            auth_url = self.os_service_endpoint
        else:
            auth_url = kwargs.get('auth_url', self.conf.auth_url)
            if auth_url is None:
                auth_url = self.os_service_endpoint + '/v%s' % version
            # Switch keyword names on version
            #  - keystoneclient.auth.identity.v3.Password minds about this
            #  - not keystoneauth1.loading._plugins.identity.generic.Password
            if version[0] == '2':
                auth_args['tenant_name'] = self.conf.tenant_name or\
                                             self.conf.project_name
            elif version[0] == '3':
                # v2 doesn't like *_domain_* vars
                # keystoneauth1.exceptions.discovery.DiscoveryFailure: Cannot use v2 authentication with domain scope
                auth_args.update({
                    'user_domain_id': 'default',
                    'project_domain_name': 'default',
                    'project_name': self.conf.project_name,
                })
            else:
                # TODO: Possible to use discovered versions if discovery is on
                raise Exception('Unsupported version %s' % version)
        auth_args['auth_url'] = auth_url
        return auth_args

    def _get_password_auth(self, **kwargs):
        version = self.conf.os_identity_api_version
        if version[0] == '3':
            auth = v3.Password(**self._get_auth_args(version=version,
                                                     **kwargs))
        elif version[0] == '2':
            auth = v2.Password(**self._get_auth_args(version=version,
                                                     **kwargs))
        else:
            raise Exception('Version %s not supported.' % VERSION)
        return auth

    def Client(self):
        sess = None
        keystone = None
        version = self.conf.os_identity_api_version
        # switch on keystoneauth1
        if self.conf.use_keystoneauth1:
            globals()['v2'] = authv2
            globals()['v3'] = authv3
            globals()['session'] = auth_session

            if self.conf.keystoneauth1.use_loading:
                if self.conf.debug:
                    plugin_loaders = loading.get_available_plugin_loaders()
                    avail_plugins = loading.get_available_plugin_names()
                    logger.debug('Available plugin loaders: %s' %
                                 sorted(plugin_loaders.iteritems()))
                    logger.debug('Available plugins: %s' % sorted(avail_plugins))
                loader = loading.get_plugin_loader('password')
                self.logger.debug('loader: %s' % loader)
                auth_args = self._get_auth_args()
                auth = loader.load_from_options(**auth_args)
                # Discover with session
                if self.conf.keystoneauth1.use_discovery:
                    if self.conf.null_session_discovery:
                        # gem from ceilometerclient.client...
                        s = session.Session()
                    else:
                        s = session.Session(auth=auth)
                    discover = kauth_discover.Discover(session=s,
                                                       url=self.os_service_endpoint)
                    self.logger.debug('discover: %s' % discover)
                    self.logger.debug('discovered version data: %s' %
                                      discover.version_data())
                    disc_auth_url = discover.url_for(version)
                    self.logger.debug('discovered urls: %s' % disc_auth_url)
                    # Re-init auth args and auth...
                    #  Not doing this generates interesting error using Identity v3: (remove and attempt v2 for magic!!)
                    #  keystoneauth1.exceptions.http.Forbidden: You are not authorized to perform the requested action: identity:list_projects
                    auth_kwargs = self._get_auth_args(auth_url=disc_auth_url,
                                                      version=version)
                    auth = loader.load_from_options(**auth_kwargs)
                else:
                    raise Exception('Non-discovery approach not implemented.')
            else:
                auth = self._get_password_auth()

            if not self.conf.keystoneauth1.use_sessions:
                raise Exception('Non-session approach not supported.')
            sess = session.Session(auth=auth)
            keystone = keystoneclient.client.Client(version, session=sess)
        else:
            # Using deprecated keystoneclient mechanisms
            # TODO: try generic passwords -- not possible w/o keystoneauth1
            auth = self._get_password_auth()
            if self.conf.keystoneclient.use_sessions:
                # TODO: use discovery
                if self.conf.keystoneclient.use_discovery:
                    # ^^^ seems not possible without versioned urls?
                    # auth_args = self._get_auth_args(self.conf.os_identity_api_version)
                    auth_args = self._get_auth_args()
                    # TODO: could i use keystoneauth1 loading here...?
                    auth = self._get_password_auth(**auth_args)
                    sess = legacy_session.Session(auth=auth)
                    # /home/kmidzi/projects/rdtibcc-679/local/lib/python2.7/site-packages/keystoneclient/session.py:17
                    # what is implication of import keystoneauth1? advent?
                    try:
                        discover = ks_discover.Discover(session=sess,
                                                        url=self.os_service_endpoint)
                        self.logger.debug('discover: %s' % discover)
                        self.logger.debug('discovered version data: %s' %
                                          discover.version_data())
                        disc_auth_url = discover.url_for(version)
                        self.logger.debug('discovered urls: %s' % disc_auth_url)
                    except Exception as e:
                        raise(Exception('Could not discover: %s' % e.message))
                else:
                    sess = keystoneclient.session.Session(auth=auth)
                # keystoneclient.exceptions.DiscoveryFailure: Not enough information to determine URL. Provide either auth_url or endpoint
                keystone = keystoneclient.client.Client(version, session=sess)
            else:
                raise Exception('Non-session approach not implemented.')

        self.logger.info('Auth object: %s' % auth)
        self.logger.info('Session object: %s' % sess)
        return keystone


if __name__ == '__main__':
    IGNORED_WARNINGS = ('InsecurePlatformWarning', 'SNIMissingWarning')
    import requests

    for w in IGNORED_WARNINGS:
        cls = getattr(requests.packages.urllib3.exceptions, w, None)
        if cls is not None:
            requests.packages.urllib3.disable_warnings(cls)

    try:
        auth_switcher = AuthSwitcher()
        auth_switcher.configure(sys.argv[1:])
    except (cfg.Error) as e:
        sys.exit(e)
    logger = auth_switcher.logger
    auth_switcher.conf.log_opt_values(logger=logger, lvl=logging.INFO)

    def list_projects(auth):
        version = auth.conf.os_identity_api_version
        keystone = auth.Client()
        if version == '2.0':
            return keystone.tenants.list()
        elif version == '3':
            return keystone.projects.list()

    sys.exit(logger.info('Projects class: %s' %
                         type(list_projects(auth_switcher)[0])))

# vim:ts=4:sw=4:shiftround:et:smartindent
