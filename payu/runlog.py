"""payu.runlog
   ===========

   Experiment run logging manager

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details.
"""

# Standard Library
import datetime
import json
import os
import shlex
import subprocess as sp
import urllib2  # TODO get rid of this

# Third party
import requests

# Local
from payu.fsops import DEFAULT_CONFIG_FNAME


class Runlog(object):

    def __init__(self, expt):

        # Disable user's global git rc file
        os.environ['GIT_CONFIG_NOGLOBAL'] = 'yes'

        self.expt = expt

        self.manifest = []
        self.create_manifest()

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
        payu_remote_name = 'payu'
        account_name = 'mxw900-raijin'
        account_url = 'https://github.com/' + account_name

        github_username = raw_input("Enter github username: ")
        github_password = raw_input("Enter github password: ")

        # Check if remote is set
        git_remotes = sp.check_output(shlex.split('git remote'),
                                      cwd=self.expt.control_path).split()

        if not payu_remote_name in git_remotes:
            payu_remote_url = account_url + self.expt.name + '.git'
            cmd = 'git remote add {} {}'.format(
                    payu_remote_name, payu_remote_url)
            sp.check_call(shlex.split(cmd))

        # Create the remote repository if needed
        repo_url = 'https://api.github.com/orgs/{}/repos'.format(account_name)

        # TODO: Use requests
        repo_response = urllib2.urlopen(repo_url)
        repos = json.loads(repo_response.read())

        if not self.expt.name in repos:
            req_data = {
                    'name': self.expt.name,
                    'description': 'Generic payu experiment',
                    'private': False,
                    'has_issues': True,
                    'has_downloads': True,
                    'has_wiki': False
            }

            resp = requests.post(repo_url, json.dumps(req_data),
                                 auth=(github_username, github_password))

        # Push to remote
        cmd = 'git push payu'
        rc = sp.call(shlex.split(cmd))
