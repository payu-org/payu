"""payu.models.staged_cable
   ================

   Driver interface to CABLE-POP_TRENDY branch

   :copyright: Copyright 2021 Marshall Ward, see AUTHORS for details
   :license: Apache License, Version 2.0, see LICENSE for details
"""

# Standard Library
import os
import shutil
import itertools

# Extensions
import f90nml
import yaml

# Local
from payu.models.model import Model
from payu.fsops import mkdir_p


def deep_update(d_1, d_2):
    """Deep update of namelists."""
    for key, value in d_2.items():
        if isinstance(value, dict):
            # Nested struct
            if key in d_1:
                # If the master namelist contains the key, then recursively
                # apply
                deep_update(d_1[key], d_2[key])
            else:
                # Otherwise just set the value from the patch dict
                d_1[key] = value
        else:
            # Is value, just override
            d_1[key] = value


class StagedCable(Model):
    """A driver for running staged CABLE spin-up configurations."""

    def __init__(self, expt, name, config):
        super(StagedCable, self).__init__(expt, name, config)

        self.model_type = 'staged_cable'
        self.default_exec = 'cable'

        self.config_files = ['stage_config.yaml']
        self.optional_config_files = ['cable.nml', 'cru.nml',
                                      'luc.nml', 'met_names.nml']

        self.configuration_log = {}

        if not os.path.isfile('configuration_log.yaml'):
            # Build a new configuration log
            self._build_new_configuration_log()
        else:
            # Read the current configuration log
            self._read_configuration_log()

        # Now set the number of runs using the configuration_log
        remaining_stages = len(self.configuration_log['queued_stages'])
        print("Overriding the remaining number of runs according to the " +
              "number of queued stages in the configuration log.")
        os.environ['PAYU_N_RUNS'] = str(remaining_stages)

    def _build_new_configuration_log(self):
        """Build a new configuration log for the first stage of the run."""

        # Read the stage_config.yaml file
        with open('stage_config.yaml', 'r') as stage_conf_f:
            self.stage_config = yaml.safe_load(stage_conf_f)

        # On the first run, we need to read the 'stage_config.yaml' file.
        cable_stages = self._prepare_configuration()

        # Build the configuration log
        self.configuration_log['queued_stages'] = cable_stages
        self.configuration_log['current_stage'] = ''
        self.configuration_log['completed_stages'] = []

        self._save_configuration_log()

    def _read_configuration_log(self):
        """Read the existing configuration log."""
        with open('configuration_log.yaml') as conf_log_file:
            self.configuration_log = yaml.safe_load(conf_log_file)

    def _prepare_configuration(self):
        """Prepare the stages in the CABLE configuration."""

        # Since Python3.7, dictionary order is guaranteed so we can read
        # the entries in order without needing to supply an index
        # We just want to populate cable_stages with the list of stages
        # to run
        cable_stages = []
        for stage_name, stage_opts in self.stage_config.items():
            # Check if stage is a multi-step or single step
            if stage_name.startswith('multistep'):
                # The multi-step stage can run each internal stage
                # a different number of times. For example, a two
                # step stage may ask for the first step (S1) 5 times,
                # but the second step (S2) only 3 times. The stage
                # looks like [S1, S2, S1, S2, S1, S2, S1, S1].
                # So what we need to do is first record the number
                # of times each step is run

                # Use recipe from https://stackoverflow.com/questions/48199961
                # Turn the stages into lists of "count" length
                steps = [[step_name] * stage_opts[step_name]['count']
                         for step_name in stage_opts.keys()]

                cable_stages.extend(
                    [stage for stage in itertools.chain.from_iterable(
                        itertools.zip_longest(*steps)
                    ) if stage is not None]
                )
                # Finish handling of multistep stage

            else:
                # A single step stage, in general we only want to run this
                # once, but check for the count anyway
                cable_stages.extend([stage_name] * stage_opts['count'])

                # Finish handling of single step stage
        return cable_stages

    def setup(self):
        super(StagedCable, self).setup()

        # Prepare the namelists for the stage
        stage_name = self._get_stage_name()
        self._apply_stage_namelists(stage_name)

        # Make the logging directory
        mkdir_p(os.path.join(self.work_path, "logs"))

        # Get the additional restarts from older restart dirs
        self._get_further_restarts()

        # Make necessary adjustments to the configuration log
        self._handle_configuration_log_setup()

    def _get_further_restarts(self):
        """Get the restarts from stages further in the past where necessary."""

        # Often we take restarts from runs which are not the most recent run as
        # inputs for particular science modules, which means we have to extend
        # the existing functionality around retrieving restarts.

        # We can't supercede the parent get_prior_restart_files, since the
        # files returned by said function are prepended by
        # self.prior_restart_path, which is not desirable in this instance.

        num_completed_stages = len(self.configuration_log['completed_stages'])

        for stage_number in reversed(range(num_completed_stages - 1)):
            respath = os.path.join(
                self.expt.archive_path,
                f'restart{stage_number:03d}'
            )
            for f_name in os.listdir(respath):
                if os.path.isfile(os.path.join(respath, f_name)):
                    f_orig = os.path.join(respath, f_name)
                    f_link = os.path.join(self.work_init_path_local, f_name)
                    # Check whether a given link already exists in the
                    # manifest, so we don't write over a newer version of a
                    # restart
                    if f_link not in self.expt.manifest.manifests['restart']:
                        self.expt.manifest.add_filepath(
                            'restart',
                            f_link,
                            f_orig,
                            self.copy_restarts
                        )

    def set_model_pathnames(self):
        super(StagedCable, self).set_model_pathnames()

        self.work_restart_path = os.path.join(self.work_path, 'restart')
        self.work_output_path = os.path.join(self.work_path, 'outputs')

    def _get_stage_name(self):
        """Get the name of the stage being prepared."""

        if self.configuration_log['current_stage'] != '':
            # If the current stage is a non-empty string, it means we exited
            # during the running of the previous stage
            stage_name = self.configuration_log['current_stage']
        else:
            # Pop the stage from the list
            stage_name = self.configuration_log['queued_stages'][0]

        # Ensure the directory exists
        if not os.path.isdir(os.path.join(self.control_path, stage_name)):
            errmsg = f"""Directory containing namelists for stage {stage_name}
             does not exist."""
            raise FileNotFoundError(errmsg)

        return stage_name

    def _apply_stage_namelists(self, stage_name):
        """Apply the stage namelists to the master namelists.

        The master namelist is the namelist that exists in the control
        directory and the stage namelist exists within the directory for the
        given stage. If a master version of a given namelist does not exist,
        then the stage namelist is taken as is.

        Example:
        .
        ├── cable.nml
        └── cable_stage
            ├── cable.nml
            └── luc.nml

        In this instance, the ```cable.nml``` for ```cable_stage``` would be
        a merge of the top level ```cable.nml``` and
        ```cable_stage/cable.nml``` (with the latter taking precedence) and
        ```luc.nml``` is just ```cable_stage/luc.nml```.
        """
        namelists = os.listdir(os.path.join(self.control_path, stage_name))

        for namelist in namelists:
            write_target = os.path.join(self.work_input_path, namelist)
            stage_nml = os.path.join(self.control_path, stage_name, namelist)

            if os.path.isfile(os.path.join(self.control_path, namelist)):
                # Instance where there is a master and stage namelist
                with open(stage_nml) as stage_nml_f:
                    stage_namelist = f90nml.read(stage_nml_f)

                master_nml = os.path.join(self.control_path, namelist)
                f90nml.patch(master_nml, stage_namelist, write_target)
            else:
                # Instance where there is only a stage namelist
                shutil.copy(stage_nml, write_target)

    def _handle_configuration_log_setup(self):
        """Make appropriate adjustments to the configuration log to reflect
        that the setup of the stage is complete."""

        if self.configuration_log['current_stage'] != '':
            # If the current stage is a non-empty string, it means we exited
            # during the running of the previous stage- leave as is
            stage_name = self.configuration_log['current_stage']
        else:
            # Normal case where we just archived a successful stage.
            self.configuration_log['current_stage'] = \
                    self.configuration_log['queued_stages'].pop(0)

        self._save_configuration_log()

        # Copy the log to the work directory
        shutil.copy('configuration_log.yaml', self.work_input_path)

    def archive(self):
        """Store model output to laboratory archive and update the
configuration log."""

        # Move files from the restart directory within work to the archive
        # restart directory.
        for f in os.listdir(self.work_restart_path):
            shutil.move(os.path.join(self.work_restart_path, f),
                        self.restart_path)
        os.rmdir(self.work_restart_path)

        # Update the configuration log and save it to the working directory
        completed_stage = self.configuration_log['current_stage']
        self.configuration_log['current_stage'] = ''
        self.configuration_log['completed_stages'].append(completed_stage)

        self._save_configuration_log()

        if len(self.configuration_log["queued_stages"]) == 0:
            # Configuration successfully completed
            os.remove('configuration_log.yaml')

        super(StagedCable, self).archive()

    def collate(self):
        pass

    def _save_configuration_log(self):
        """Write the updated configuration log back to the staging area."""
        with open('configuration_log.yaml', 'w+') as config_log_f:
            yaml.dump(self.configuration_log, config_log_f)
