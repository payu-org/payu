"""Experiment run logging manager.

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
import sys

# Third party
import requests
import yaml

# Local
from payu.fsops import DEFAULT_CONFIG_FNAME

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
        runlog_config = self.expt.config.get('runlog', {})
        remote_name = runlog_config.get('remote', 'payu')

        cmd = 'ssh-agent bash -c "ssh-add ~/.ssh/id_rsa_payu; git push --all payu"'
        rc = sp.call(shlex.split(cmd), cwd=self.expt.control_path)

    # TODO: Rename this, don't pretend to be ssh-keygen
    def keygen(self):
        """Set up authentication keys and API tokens."""
        runlog_config = self.expt.config.get('runlog', {})
        expt_name = runlog_config.get('name', self.expt.name)
        expt_description = self.expt.config.get('description',
                                                'An amazing payu experiment!')

        # 0. Authentication details
        github_username = runlog_config.get('username')
        if not github_username:
            github_username = raw_input('Enter github username: ')

        github_password = getpass.getpass('Enter {}@github password: '
                                          ''.format(github_username))

        github_auth = (github_username, github_password)

        # 1. Create the organisation if needed
        github_api_url = 'https://api.github.com'
        org_name = runlog_config.get('organization')
        if org_name:
            repo_target = org_name

            # Check if org exists
            org_query_url = os.path.join(github_api_url, 'orgs', org_name)
            org_req = requests.get(org_query_url)

            if org_req.status_code == 404:
                # NOTE: Orgs cannot be created via the API
                print('payu: github organization {} does not exist.')
                print('      You must first create this on the website.')

            elif org_req.status_code == 200:
                # TODO: Confirm that the user can interact with the repo
                pass

            else:
                # TODO: Exit with grace
                print('payu: abort!')
                sys.exit(-1)

            repo_query_url = os.path.join(github_api_url, 'orgs', org_name,
                                          'repos')
            repo_api_url = os.path.join(github_api_url, 'repos', org_name,
                                        expt_name)
        else:
            repo_target = github_username

            # Create repo in user account
            repo_query_url = os.path.join(github_api_url, 'user', 'repos')
            repo_api_url = os.path.join(github_api_url, 'repos',
                                        github_username, expt_name)

        # 2. Create the remote repository
        user_repos = []
        page = 1
        while True:
            repo_params = {'page': page, 'per_page': 100}
            repo_query = requests.get(repo_query_url, auth=github_auth,
                                      params=repo_params)
            assert repo_query.status_code == 200
            if repo_query.json():
                user_repos.extend(list(r['name'] for r in repo_query.json()))
                page += 1
            else:
                break

        if expt_name not in user_repos:
            repo_config = {
                    'name': expt_name,
                    'description': expt_description,
                    'private': False,
                    'has_issues': True,
                    'has_downloads': True,
                    'has_wiki': False
            }

            repo_gen = requests.post(repo_query_url, json.dumps(repo_config),
                                     auth=github_auth)

            assert repo_gen.status_code == 201

        # 3. Check if remote is set
        git_remotes = sp.check_output(shlex.split('git remote'),
                                      cwd=self.expt.control_path).split()

        remote_name = runlog_config.get('remote', 'payu')

        if remote_name not in git_remotes:
            remote_url = os.path.join('ssh://git@github.com', repo_target,
                                      self.expt.name + '.git')
            cmd = 'git remote add {} {}'.format(remote_name, remote_url)
            sp.check_call(shlex.split(cmd), cwd=self.expt.control_path)

        # 4. Generate a payu-specific SSH key
        ssh_key = runlog_config.get('sshid', 'id_rsa_payu')
        ssh_path = os.path.join(os.path.expanduser('~'), '.ssh')

        ssh_keypath = os.path.join(ssh_path, ssh_key)
        if not os.path.isfile(ssh_keypath):
            cmd = 'ssh-keygen -t rsa -f id_rsa_payu -q -P ""'
            sp.check_call(shlex.split(cmd), cwd=ssh_path)

        # 5. Deploy key to repo
        with open(ssh_keypath + '.pub') as keyfile:
            pubkey = ' '.join(keyfile.read().split()[:-1])

        # TODO: Get this from github?
        repo_keys_url = os.path.join(repo_api_url, 'keys')
        keys_req = requests.get(repo_keys_url, auth=github_auth)
        assert keys_req.status_code == 200

        if not any(k['key'] == pubkey for k in keys_req.json()):
            add_key_param = {'title': 'payu', 'key': pubkey}
            add_key_req = requests.post(repo_keys_url, auth=github_auth,
                                        json=add_key_param)
            assert add_key_req.status_code == 201
