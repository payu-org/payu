"""Experiment post-processing - syncing archive to a remote directory

:copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

# Standard
import getpass
import glob
import os
import shutil
import subprocess


# Local
from payu.fsops import mkdir_p, list_archive_dirs
from payu.metadata import METADATA_FILENAME


class SourcePath():
    """Helper class for building rsync commands - stores attributes
    of source paths to sync.
    Note: Protected paths are paths that shouldn't be removed
    locally if still running an experiment - i.e last output or last
    permanently archived and subsequent restarts
    """
    def __init__(self, path, protected=False, is_log_file=False):
        self.protected = protected
        self.path = path
        self.is_log_file = is_log_file


class SyncToRemoteArchive():
    """Class used for archiving experiment outputs to a remote directory"""

    def __init__(self, expt):
        self.expt = expt
        self.config = self.expt.config.get('sync', {})

        # Ignore the latest output/restart if flagged
        self.ignore_last = os.environ.get('PAYU_SYNC_IGNORE_LAST', False)

        # Use configured url to flag syncing to remote machine
        self.remote_url = self.config.get('url', None)
        self.remote_syncing = self.remote_url is not None

        self.source_paths = []

    def add_outputs_to_sync(self):
        """Add paths of outputs in archive to sync. The last output is
        protected"""
        outputs = list_archive_dirs(archive_path=self.expt.archive_path,
                                    dir_type='output')
        outputs = [os.path.join(self.expt.archive_path, output)
                   for output in outputs]
        if len(outputs) > 0:
            last_output = outputs.pop()
            if not self.ignore_last:
                # Protect the last output
                self.source_paths.append(SourcePath(path=last_output,
                                                    protected=True))
        self.source_paths.extend([SourcePath(path) for path in outputs])

    def add_restarts_to_sync(self):
        """Add paths and protected paths of restarts in archive to sync.
        Last permanently-archived restart and subsequent restarts are
        protected (as local date-based restart pruning uses the last-saved
        restart as a checkpoint for a datetime)"""
        syncing_restarts = self.config.get('restarts', False)
        syncing_all_restarts = os.environ.get('PAYU_SYNC_RESTARTS', False)
        if not (syncing_all_restarts or syncing_restarts):
            return

        # Get sorted list of restarts in archive
        restarts = list_archive_dirs(archive_path=self.expt.archive_path,
                                     dir_type='restart')
        restarts = [os.path.join(self.expt.archive_path, restart)
                    for restart in restarts]
        if restarts == []:
            return

        # Find all restarts that will be 'permanently archived'
        pruned_restarts = self.expt.get_restarts_to_prune(
            ignore_intermediate_restarts=True)
        saved_restarts = [
            restart for restart in restarts
            if os.path.basename(restart) not in pruned_restarts
        ]

        # Sync only permanently saved restarts unless flagged to sync all
        to_sync = saved_restarts if not syncing_all_restarts else restarts

        # Protect last saved restart and any intermediate restarts
        if to_sync and saved_restarts:
            last_saved_index = to_sync.index(saved_restarts[-1])
            paths = to_sync[:last_saved_index]
            protected_paths = to_sync[last_saved_index:]
        else:
            protected_paths, paths = to_sync, []

        if self.ignore_last:
            # Remove the last restart from sync paths
            if protected_paths and protected_paths[-1] == restarts[-1]:
                protected_paths.pop()

        # Add to sync source paths
        self.source_paths.extend([SourcePath(path=path, protected=True)
                                  for path in protected_paths])
        self.source_paths.extend([SourcePath(path) for path in paths])

    def add_extra_source_paths(self):
        """Add additional paths to sync to remote archive"""
        paths = self.config.get('extra_paths', [])
        if isinstance(paths, str):
            paths = [paths]

        for path in paths:
            matching_paths = glob.glob(path)
            # First check if any matching paths exists
            if matching_paths:
                # Add extra paths to protected paths - so they can't be deleted
                self.source_paths.append(SourcePath(path=path, protected=True))
            else:
                print(f"payu: error: No paths matching {path} found. "
                      "Failed to sync path to remote archive")

    def set_destination_path(self):
        "set or create destination path to sync archive to"
        # Remote path to sync output to
        dest_path = self.config.get('path', None)
        if dest_path is None:
            print("There's is no configured path to sync output to. "
                  "In config.yaml, set:\n"
                  "   sync:\n      path: PATH/TO/REMOTE/ARCHIVE\n"
                  "Replace PATH/TO/REMOTE/ARCHIVE with a unique absolute path "
                  "to sync outputs to. Ensure path is unique to avoid "
                  "overwriting exsiting output!")
            raise ValueError("payu: error: Sync path is not defined.")

        if not self.remote_syncing:
            # Create local destination directory if it does not exist
            mkdir_p(dest_path)
        else:
            # Syncing to remote machine
            remote_user = self.config.get('user', None)
            if remote_user is not None:
                dest_path = f'{remote_user}@{self.remote_url}:{dest_path}'
            else:
                dest_path = f'{self.remote_url}:{dest_path}'

        self.destination_path = dest_path

    def set_excludes_flags(self):
        """Add lists of patterns of filepaths to exclude from sync commands"""
        # Get any excludes
        exclude = self.config.get('exclude', [])
        if isinstance(exclude, str):
            exclude = [exclude]

        excludes = ' '.join(['--exclude ' + pattern for pattern in exclude])

        # Default to exclude uncollated files if collation is enabled
        # This can be over-riden using exclude_uncollated config flag
        exclude_uncollated = self.config.get('exclude_uncollated', None)

        if exclude_uncollated is None:
            collate_config = self.expt.config.get('collate', {})
            collating = collate_config.get('enable', True)
            if collating:
                exclude_uncollated = True

        exclude_flag = "--exclude *.nc.*"
        if (exclude_uncollated and exclude_flag not in excludes
                and exclude_flag not in self.config.get('rsync_flags', [])):
            excludes += " --exclude *.nc.*"

        self.excludes = excludes

    def build_cmd(self, source_path):
        """Given a source path to sync, return a rsync command"""
        if source_path.protected:
            # No local delete option for protected paths
            cmd = f'{self.base_rsync_cmd} {self.excludes} '
        elif source_path.is_log_file:
            cmd = f'{self.base_rsync_cmd} {self.remove_files} '
        else:
            cmd = f'{self.base_rsync_cmd} {self.excludes} {self.remove_files} '

        cmd += f'{source_path.path} {self.destination_path}'
        return cmd

    def run_cmd(self, source_path):
        """Given an source path, build and run rsync command"""
        cmd = self.build_cmd(source_path)
        print(cmd)
        try:
            subprocess.check_call(cmd, shell=True)
        except subprocess.CalledProcessError as e:
            print('payu: Error rsyncing archive to remote directory: '
                  f'Failed running command: {cmd}.')
            # TODO: Raise or return?
            return

        if not source_path.protected and self.remove_local_dirs:
            # Only delete real directories; ignore symbolic links
            path = source_path.path
            if os.path.isdir(path) and not os.path.islink(path):
                print(f"Removing {path} from local archive")
                shutil.rmtree(path)

    def git_runlog(self):
        """Add git runlog to remote archive"""
        add_git_runlog = self.config.get("runlog", True)

        if add_git_runlog:
            # Currently runlog is only set up for local remote archive
            if self.remote_syncing:
                print("payu: error: Syncing the git runlog is not implemented "
                      "for syncing to a remote machine")
                return

            control_path = self.expt.control_path
            runlog_path = os.path.join(self.destination_path, "git-runlog")
            if not os.path.exists(runlog_path):
                # Create a bare repository, if it doesn't exist
                try:
                    print("Creating git-runlog bare repository clone"
                          f" at {runlog_path}")
                    cmd = f"git clone --bare {control_path} {runlog_path}"
                    subprocess.check_call(cmd, shell=True)
                except subprocess.CalledProcessError as e:
                    print("payu: error: Failed to create a bare repository. ",
                          f"Error: {e}")
                    return
            else:
                # Update bare gitlog repo
                try:
                    print(f"Updating git-runlog at {runlog_path}")
                    cmd = f"git push {runlog_path}"
                    subprocess.check_call(cmd, shell=True, cwd=control_path)
                except subprocess.CalledProcessError as e:
                    print("payu: error: Failed to push git runlog to bare "
                          f"repository. Error: {e}")

    def run(self):
        """Build and run rsync cmds to remote remote archive """
        # Add outputs and restarts to source paths to sync
        self.add_outputs_to_sync()
        self.add_restarts_to_sync()

        # Add pbs and error logs to paths
        for log_type in ['error_logs', 'pbs_logs']:
            log_path = os.path.join(self.expt.archive_path, log_type)
            if os.path.isdir(log_path):
                self.source_paths.append(SourcePath(path=log_path,
                                                    is_log_file=True))

        # Add metadata path to protected paths, if it exists
        metadata_path = os.path.join(self.expt.archive_path, METADATA_FILENAME)
        if os.path.isfile(metadata_path):
            self.source_paths.append(SourcePath(path=metadata_path,
                                                protected=True))

        # Add any additional paths to protected paths
        self.add_extra_source_paths()

        # Set rsync command components
        self.set_destination_path()
        self.set_excludes_flags()

        # Set base rsync command
        default_flags = '-vrltoD --safe-links'
        rsync_flags = self.config.get('rsync_flags', default_flags)
        self.base_rsync_cmd = f'rsync {rsync_flags}'

        # Set remove local files/dirs options
        remove_files = self.config.get('remove_local_files', False)
        self.remove_files = '--remove-source-files' if remove_files else ''
        self.remove_local_dirs = self.config.get('remove_local_dirs', False)

        # Build and run all rsync commands
        for source_path in self.source_paths:
            self.run_cmd(source_path)

        # Add git runlog to remote archive
        self.git_runlog()
