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
import git

# Third party
import requests

# Local
from payu.fsops import DEFAULT_CONFIG_FNAME
from payu.git_utils import GitRepository, get_git_repository


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
        """Commit the runlog changes to the git repository."""
        # Check if a repository exists, otherwise initialise one.
        git_repo = GitRepository(self.expt.control_path, catch_error=True)
        if git_repo.repo is None:
            git_repo.repo = get_git_repository(self.expt.control_path, initialise=True)

        # Create commit message with timestamp and file to add to the commit
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        commit_msg = '{0}: Run {1}'.format(timestamp, self.expt.counter)

        paths_to_add = [f for f in self.manifest if os.path.isfile(f)]

        # Commit the runlog changes
        try:
            git_repo.commit(commit_msg, paths_to_add)
        except git.exc.GitCommandError as e:
            try:
                git_repo.repo.git.add(paths_to_add)
                git_repo.repo.git.commit(m=commit_msg, no_gpg_sign=True)
                warnings.warn("Runlog commit without gpg signing.")
            except git.exc.GitCommandError as e:
                print(f"payu: error: Failed to commit runlog changes to git repository: {e}.")

        # Save the commit hash
        self.expt.run_id = git_repo.repo.head.object.hexsha

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

        ssh_cmd = f'ssh -i {ssh_key_path}'
        git_repo = GitRepository(self.expt.control_path, catch_error=True)
        with git_repo.git.custom_environment(GIT_SSH_COMMAND=ssh_cmd):
            try:
                remote = git_repo.repo.remotes.payu
                remote.push(all=True)
            except Exception as e:
                print(f"payu: error: Failed to push runlog changes to remote repository: {e}.")


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
        remote_name = self.config.get('remote', 'payu')
        remote_url = os.path.join('ssh://git@github.com', repo_target, self.expt.name + '.git')

        git_repo = GitRepository(self.expt.control_path, catch_error=True)
        git_remote = {r.name: r.url for r in git_repo.repo.remotes} if git_repo else {}

        if remote_name not in git_remote:
            git_repo.repo.create_remote(remote_name, remote_url)

        elif git_remote[remote_name] != remote_url:
            print('payu: error: Existing remote URL does not match '
                  'the proposed URL.')
            print('payu: error: To delete the old remote, type '
                  '`git remote rm {name}`.'.format(name=remote_name))
            sys.exit(-1)

        # 4. Generate a payu-specific SSH key
        default_ssh_key = 'id_rsa_payu_' + expt_name
        ssh_key = self.config.get('sshid', default_ssh_key)
        ssh_dir = os.path.join(os.path.expanduser('~'), '.ssh', 'payu')
        os.makedirs(ssh_dir, exist_ok=True)

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
