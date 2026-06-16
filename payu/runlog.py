"""Experiment run logging manager.

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

# Standard Library
import datetime
import os
import warnings
import git

# Local
from payu.fsops import DEFAULT_CONFIG_FNAME
from payu.git_utils import GitRepository, get_git_repository


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
            warnings.warn(f"Failed to commit runlog changes to git repository: {e}.")

        # Save the commit hash
        self.expt.run_id = git_repo.get_hash()

    def push(self):
        """Push the changes to the remote repository.

        Usage: payu push

        This command pushes local runlog changes to the remote runlog
        repository, currently named `payu`, using the SSH key associated with
        this experiment.
        """
        git_repo = GitRepository(self.expt.control_path, catch_error=True)
        try:
            remote = git_repo.repo.remotes.payu
            remote.push(all=True)
        except Exception as e:
            print(f"payu: error: Failed to push runlog changes to remote repository: {e}.")

