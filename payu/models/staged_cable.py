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

        # Read the stage_config.yaml file
        with open('stage_config.yaml', 'r') as stage_conf_f:
            self.stage_config = yaml.safe_load(stage_conf_f)

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

        # On the first run, we need to read the 'stage_config.yaml' file.
        cable_stages = self._prepare_configuration()

        # Build the configuration log
        self.configuration_log['queued_stages'] = cable_stages
        self.configuration_log['current_stage'] = ''
        self.configuration_log['completed_stages'] = []

        with open('configuration_log.yaml', 'w') as conf_log_file:
            yaml.dump(self.configuration_log, conf_log_file)

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

        # Directories required by CABLE for outputs
        for _dir in ['logs', 'restart', 'outputs']:
            os.makedirs(os.path.join(self.work_output_path, _dir),
                        exist_ok=True)

        self._prepare_stage()

    def get_prior_restart_files(self):
        """Retrieve the prior restart files from the completed stages."""
        # Go to the archives of the previous completed stages and retrieve
        # the files from them, with the most recent taking precedent.

        # Unfortunately, we can't simply use the
        # "if {filename} not in {restart_files}, because files from different
        # stages will have different paths, even if the local file name is the
        # same. To avoid having to call os.path.basepath on the list of restart
        # files for every addition, we'll store the list of local file names +
        # paths separately, and pull them together at the end.

        file_names = []
        path_names = []

        num_completed_stages = len(self.configuration_log['completed_stages'])

        for stage_number in reversed(range(num_completed_stages)):
            respath = os.path.join(
                self.control_path,
                f'archive/output{stage_number:03d}/restart'
            )

            [(file_names.append(file), path_names.append(respath))
                for file in os.listdir(respath) if file not in file_names]

        # Zip up the files
        restart_files = [os.path.join(path, file)
                         for path, file in zip(path_names, file_names)]

        return restart_files

    def _prepare_stage(self):
        """Apply the stage namelist to the master namelist."""

        if self.configuration_log['current_stage'] != '':
            # If the current stage is a non-empty string, it means we exited
            # during the running of the previous stage
            stage_name = self.configuration_log['current_stage']
        else:
            # Pop the stage from the list
            stage_name = self.configuration_log['queued_stages'].pop(0)
            self.configuration_log['current_stage'] = stage_name

        with open('configuration_log.yaml', 'w') as conf_log_f:
            yaml.dump(self.configuration_log, conf_log_f)

        # Ensure the directory exists
        if not os.path.isdir(os.path.join(self.control_path, stage_name)):
            errmsg = f"""Directory containing namelists for stage {stage_name}
             does not exist."""
            raise FileNotFoundError(errmsg)

        # Apply the stage namelists
        self._apply_stage_namelists(stage_name)

        # Copy the log to the work directory
        shutil.copy('configuration_log.yaml', self.work_input_path)

    def _apply_stage_namelists(self, stage_name):
        """Apply the stage namelists to the master namelists."""
        namelists = os.listdir(os.path.join(self.control_path, stage_name))

        for namelist in namelists:
            write_target = os.path.join(self.work_input_path, namelist)
            stage_nml = os.path.join(self.control_path, stage_name, namelist)
            with open(stage_nml) as stage_nml_f:
                stage_namelist = f90nml.read(stage_nml_f)

            master_nml = os.path.join(self.control_path, namelist)
            f90nml.patch(master_nml, stage_namelist, write_target)

    def archive(self):
        """Store model output to laboratory archive and update the
configuration log."""

        # Update the configuration log and save it to the working directory
        completed_stage = self.configuration_log['current_stage']
        self.configuration_log['current_stage'] = ''
        self.configuration_log['completed_stages'].append(completed_stage)

        self._save_configuration_log()

        if int(os.environ['PAYU_N_RUNS']) == 0:
            os.remove('configuration_log.yaml')

        super(StagedCable, self).archive()

    def collate(self):
        pass

    def _save_configuration_log(self):
        """Write the updated configuration log back to the staging area."""
        with open('configuration_log.yaml', 'w+') as config_log_f:
            yaml.dump(self.configuration_log, config_log_f)
