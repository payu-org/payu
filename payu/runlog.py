"""payu.runlog
   ===========

   Experiment run logging manager

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details.
"""

# Standard Library
import datetime
import getpass
import json
import os
import shlex
import stat
import subprocess as sp

# Third party
import requests
import yaml

# Local
from payu.fsops import DEFAULT_CONFIG_FNAME

# Fingerprints (unique identifiers for API tokens)
TOKEN_FINGERPRINT = 'Kv5qbBj096cdAkltffQS/vAxUQxRD0VH+N5qVG8QMWw='

# Miscellaneous
PAYU_URL = 'https://github.com/marshallward/payu'

class Runlog(object):

    def __init__(self, expt):

        # Disable user's global git rc file
        os.environ['GIT_CONFIG_NOGLOBAL'] = 'yes'

        self.expt = expt

        self.manifest = []
        self.create_manifest()

        self.payu_config_dir = os.path.join(os.path.expanduser('~'), '.payu')
        self.token_path = os.path.join(self.payu_config_dir, 'tokens.yaml')

    def create_manifest(self):

        config_path = os.path.join(self.expt.control_path,
                                   DEFAULT_CONFIG_FNAME)

        if os.path.isfile(config_path):
            self.manifest.append(config_path)

        for model in self.expt.models:
            config_files = model.config_files + model.optional_config_files

            self.manifest.extend(os.path.join(model.control_path, f)
                                 for f in config_files)

    def commit(self):
        f_null = open(os.devnull, 'w')

        # Check if a repository exists
        cmd = 'git rev-parse'
        print(cmd)
        rc = sp.call(shlex.split(cmd), stdout=f_null,
                     cwd=self.expt.control_path)
        if rc:
            cmd = 'git init'
            print(cmd)
            sp.check_call(shlex.split(cmd), stdout=f_null,
                          cwd=self.expt.control_path)

        # Add configuration files
        for fname in self.manifest:
            if os.path.isfile(fname):
                cmd = 'git add {}'.format(fname)
                print(cmd)
                sp.check_call(shlex.split(cmd), stdout=f_null,
                              cwd=self.expt.control_path)

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        commit_msg = '{}: Run {}'.format(timestamp, self.expt.counter)

        cmd = 'git commit -am "{}"'.format(commit_msg)
        print(cmd)
        try:
            sp.check_call(shlex.split(cmd), stdout=f_null,
                          cwd=self.expt.control_path)
        except sp.CalledProcessError:
            print('TODO: Check if commit is unchanged')

        f_null.close()

    def push(self):
        # Test variables
        runlog_config = self.expt.config.get('runlog', {})
        remote_name = runlog_config.get('remote', 'payu')

        github_expt_name = runlog_config.get('name', self.expt.name)
        github_org = runlog_config.get('organization')

        # The API uses https, git is using ssh
        # It would be nice to exclusively use the API, but it is currently not
        # clear how to push without exposing the token in the remote

        #org_url = 'https://github.com/' + github_org
        org_ssh = 'ssh://git@github.com/' + github_org
        repo_api_url = ('https://api.github.com/orgs/{}/repos'
                        ''.format(github_org))

        # Check if remote is set
        git_remotes = sp.check_output(shlex.split('git remote'),
                                      cwd=self.expt.control_path).split()

        if remote_name not in git_remotes:
            remote_url = os.path.join(org_ssh, self.expt.name + '.git')
            cmd = 'git remote add {} {}'.format(remote_name, remote_url)
            sp.check_call(shlex.split(cmd), cwd=self.expt.control_path)

        # Create the remote repository if needed
        resp = requests.get(repo_api_url)

        if not any(r['name'] == github_expt_name for r in resp.json()):
            # TODO: Set this with config.yaml
            req_data = {
                    'name': github_expt_name,
                    'description': 'Generic payu experiment',
                    'private': False,
                    'has_issues': True,
                    'has_downloads': True,
                    'has_wiki': False
            }

            # Credentials
            github_username = runlog_config.get('username')
            # TODO: Check for interactive session
            if not github_username:
                github_username = raw_input('Enter github username: ')

            with open(self.token_path) as token_file:
                token_config = yaml.load(token_file)
                github_token = token_config['github']

            resp = requests.post(repo_api_url, json.dumps(req_data),
                                 auth=(github_username, github_token))

        # Push to remote
        cmd = 'git push --all {}'.format(remote_name)
        rc = sp.call(shlex.split(cmd), cwd=self.expt.control_path)

    def keygen(self):
        """Set up authentication keys and API tokens."""
        runlog_config = self.expt.config.get('runlog', {})

        # Get username and password
        github_username = runlog_config.get('username')
        if not github_username:
            github_username = raw_input('Enter github username: ')

        github_password = getpass.getpass('Enter {}@github password: '
                                          ''.format(github_username))

        github_auth = (github_username, github_password)

        # Check if token API exists
        auth_url = 'https://api.github.com/authorizations'
        req = requests.get(auth_url, auth=github_auth)
        assert req.status_code == 200

        if any(t for t in req.json() if t['fingerprint'] == TOKEN_FINGERPRINT):
            # TODO: Validate the existing token; if broken, make a new one
            print('payu: github API token already exists.')

        else:
            # Generate a new API token
            auth_param = {
                'scopes': ['repo', 'admin:org_hook'],
                'note': 'Payu runlog synchronization',
                'note_url': PAYU_URL,
                'fingerprint': TOKEN_FINGERPRINT,
            }

            req = requests.post(auth_url, json=auth_param, auth=github_auth)
            assert req.status_code == 201
            token = req.json()['token']

            # Setup the config directory
            if not os.path.isdir(self.payu_config_dir):
                os.makedirs(self.payu_config_dir)
                os.chmod(self.payu_config_dir, stat.S_IRWXU)

            # Save token to secret file
            if os.path.isfile(self.token_path):
                print('payu: Replacing old github API token')
                os.remove(self.token_path)

            token_data = {'tokens': {'github': token}}
            with open(self.token_path, 'w') as token_file:
                yaml.dump(token_data, token_file, default_flow_style=True)

            os.chmod(self.token_path, stat.S_IRUSR | stat.S_IWUSR)

        # TODO: Now generate an ssh key
