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
import subprocess
import sys
import warnings

# Third party
import requests

# Local
from payu.fsops import DEFAULT_CONFIG_FNAME
from payu.fsops import mkdir_p


# Compatibility
try:
    input = raw_input
except NameError:
    pass


class Runlog(object):
    def __init__(self, expt):
        # Disable user's global git rc file
        os.environ['GIT_CONFIG_NOGLOBAL'] = 'yes'

        self.expt = expt

        # Fetch and update the runlog config
        runlog_config = self.expt.config.get('runlog', {})
        if isinstance(runlog_config, bool):
            self.enabled = runlog_config
            runlog_config = {}
        else:
            assert isinstance(runlog_config, dict)
            self.enabled = runlog_config.pop('enable', True)
        self.config = runlog_config

        self.manifest = []

        self.payu_config_dir = os.path.join(os.path.expanduser('~'), '.payu')
        self.token_path = os.path.join(self.payu_config_dir, 'tokens.yaml')

    def create_manifest(self):
        """Construct the list of files to be tracked by the runlog."""
        config_path = os.path.join(self.expt.control_path,
                                   DEFAULT_CONFIG_FNAME)

        self.manifest = []

        if os.path.isfile(config_path):
            self.manifest.append(config_path)

        for model in self.expt.models:
            config_files = model.config_files + model.optional_config_files

            self.manifest.extend(os.path.join(model.control_path, f)
                                 for f in config_files)

        # Add file manifests to runlog manifest
        for mf in self.expt.manifest:
            self.manifest.append(mf.path)

    def commit(self):
        f_null = open(os.devnull, 'w')

        # Check if a repository exists
        if commit_hash(self.expt.control_path) is None:
            cmd = 'git init'
            print(cmd)
            subprocess.check_call(shlex.split(cmd), stdout=f_null,
                                  cwd=self.expt.control_path)

        # Add configuration files
        for fname in self.manifest:
            if os.path.isfile(fname):
                cmd = 'git add {0}'.format(fname)
                print(cmd)
                subprocess.check_call(shlex.split(cmd), stdout=f_null,
                                      cwd=self.expt.control_path)

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        commit_msg = '{0}: Run {1}'.format(timestamp, self.expt.counter)

        cmd = 'git commit -am "{0}"'.format(commit_msg)
        print(cmd)
        try:
            subprocess.check_call(shlex.split(cmd), stdout=f_null,
                                  stderr=f_null, cwd=self.expt.control_path)
        except subprocess.CalledProcessError:
            # Attempt commit without signing commits
            cmd = f'git commit --no-gpg-sign -am "{commit_msg}"'
            print(cmd)
            try:
                subprocess.check_call(shlex.split(cmd),
                                      stdout=f_null,
                                      cwd=self.expt.control_path)
                warnings.warn("Runlog commit was commited without git signing")
            except subprocess.CalledProcessError:
                warnings.warn("Error occured when attempting to commit runlog")

        # Save the commit hash
        self.expt.run_id = commit_hash(self.expt.control_path)

        f_null.close()

    def push(self):
        """Push the changes to the remote repository.

        Usage: payu push

        This command pushes local runlog changes to the remote runlog
        repository, currently named `payu`, using the SSH key associated with
        this experiment.

        For an experiment `test`, it is equivalent to the following command::

            ssh-agent bash -c "
                ssh-add $HOME/.ssh/payu/id_rsa_payu_test
                git push --all payu
            "
        """
        expt_name = self.config.get('name', self.expt.name)

        default_ssh_key = 'id_rsa_payu_' + expt_name
        ssh_key = self.config.get('sshid', default_ssh_key)
        ssh_key_path = os.path.join(os.path.expanduser('~'), '.ssh', 'payu',
                                    ssh_key)

        if not os.path.isfile(ssh_key_path):
            print('payu: error: Github SSH key {key} not found.'
                  ''.format(key=ssh_key_path))
            print('payu: error: Run `payu ghsetup` to generate a new key.')
            sys.exit(-1)

        cmd = ('ssh-agent bash -c "ssh-add {key}; git push --all payu"'
               ''.format(key=ssh_key_path))
        subprocess.check_call(shlex.split(cmd), cwd=self.expt.control_path)

    def github_setup(self):
        """Set up authentication keys and API tokens."""
        github_auth = self.authenticate()
        github_username = github_auth[0]

        expt_name = self.config.get('name', self.expt.name)
        expt_description = self.expt.config.get('description')
        if not expt_description:
            expt_description = input('Briefly describe the experiment: ')
            assert isinstance(expt_description, str)
        expt_private = self.config.get('private', False)

        # 1. Create the organisation if needed
        github_api_url = 'https://api.github.com'
        org_name = self.config.get('organization')
        if org_name:
            repo_target = org_name

            # Check if org exists
            org_query_url = os.path.join(github_api_url, 'orgs', org_name)
            org_req = requests.get(org_query_url)

            if org_req.status_code == 404:
                # NOTE: Orgs cannot be created via the API
                print('payu: github organization {org} does not exist.'
                      ''.format(org=org_name))
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
                'private': expt_private,
                'has_issues': True,
                'has_downloads': True,
                'has_wiki': False
            }

            repo_gen = requests.post(repo_query_url, json.dumps(repo_config),
                                     auth=github_auth)

            assert repo_gen.status_code == 201

        # 3. Check if remote is set
        git_remote_out = subprocess.check_output(shlex.split('git remote -v'),
                                                 cwd=self.expt.control_path)

        git_remotes = dict([(r.split()[0], r.split()[1])
                            for r in git_remote_out.split('\n') if r])

        remote_name = self.config.get('remote', 'payu')
        remote_url = os.path.join('ssh://git@github.com', repo_target,
                                  self.expt.name + '.git')

        if remote_name not in git_remotes:
            cmd = ('git remote add {name} {url}'
                   ''.format(name=remote_name, url=remote_url))
            subprocess.check_call(shlex.split(cmd), cwd=self.expt.control_path)
        elif git_remotes[remote_name] != remote_url:
            print('payu: error: Existing remote URL does not match '
                  'the proposed URL.')
            print('payu: error: To delete the old remote, type '
                  '`git remote rm {name}`.'.format(name=remote_name))
            sys.exit(-1)

        # 4. Generate a payu-specific SSH key
        default_ssh_key = 'id_rsa_payu_' + expt_name
        ssh_key = self.config.get('sshid', default_ssh_key)
        ssh_dir = os.path.join(os.path.expanduser('~'), '.ssh', 'payu')
        mkdir_p(ssh_dir)

        ssh_keypath = os.path.join(ssh_dir, ssh_key)
        if not os.path.isfile(ssh_keypath):
            cmd = 'ssh-keygen -t rsa -f {key} -q -P ""'.format(key=ssh_key)
            subprocess.check_call(shlex.split(cmd), cwd=ssh_dir)

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

    def authenticate(self):
        # TODO: Password authentication will not work if one is using
        # two-factor authentication.  In this case, an API token is needed.

        github_username = self.config.get('username')
        if not github_username:
            github_username = input('Enter GitHub username: ')

        github_password = getpass.getpass('Enter {username}@github password: '
                                          ''.format(username=github_username))

        github_auth = (github_username, github_password)
        return github_auth


# Some git utility functions

def commit_hash(dir='.'):
    """
    Return commit hash for HEAD of checked out branch of the
    specified directory.
    """

    cmd = ['git', 'rev-parse', 'HEAD']

    try:
        with open(os.devnull, 'w') as devnull:
            revision_hash = subprocess.check_output(
                cmd,
                cwd=dir,
                stderr=devnull
            )
        if sys.version_info.major > 2:
            revision_hash = revision_hash.decode('ascii')

        return revision_hash.strip()

    except subprocess.CalledProcessError:
        return None
