"""payu.models.cable
   ================

   Driver interface to CABLE-POP_TRENDY branch

   :copyright: Copyright 2021 Marshall Ward, see AUTHORS for details
   :license: Apache License, Version 2.0, see LICENSE for details
"""

# Standard Library
import os
import shutil

# Extensions
import f90nml
import yaml
# import xarray

# Local
from payu.models.model import Model


def deep_update(d_1, d_2):
    """Deep update of namelists."""
    for key, value in d_2.items():
        if isinstance(value, dict):
            deep_update(d_1[key], d_2[key])
        else:
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

        # Add the restart directories to inputs
        num_completed_stages = len(self.configuration_log['completed_stages'])
        for restart_dir in reversed(range(num_completed_stages)):
            config['input'].append(os.path.realpath(
                f'archive/output{restart_dir:03d}/restart'))

        # Now set the number of runs using the configuration_log
        remaining_stages = len(self.configuration_log['queued_stages'])
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
                step_names = []
                step_counts = []
                for step_name, step_opts in stage_opts.items():
                    step_names.append(step_name)
                    step_counts.append(step_opts['count'])

                # Now iterate to the maximum number of steps
                for step in range(max(step_counts)):
                    for step_id, _ in enumerate(step_names):
                        if step_counts[step_id] > step:
                            cable_stages.append(step_names[step_id])
            # Finish handling of multistep stage

            else:
                # A single step stage, in general we only want to run this
                # once, but check for the count anyway
                for _ in range(stage_opts['count']):
                    cable_stages.append(stage_name)

        # Finish handling of single step stage
        return cable_stages

    def setup(self):
        super(StagedCable, self).setup()

        # Directories required by CABLE for outputs
        os.makedirs(os.path.join(self.work_output_path, 'logs'),
            exist_ok = True)
        os.makedirs(os.path.join(self.work_output_path, 'restart'),
            exist_ok = True)
        os.makedirs(os.path.join(self.work_output_path, 'outputs'),
            exist_ok = True)

        self._prepare_stage()

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
        if not os.path.isdir(stage_name):
            errmsg = f"""Directory containing namelists for stage {stage_name}
             does not exist."""
            raise FileNotFoundError(errmsg)

        # Apply the stage namelists
        self._apply_stage_namelists(stage_name)

        # Copy the log to the work directory
        shutil.copy('configuration_log.yaml', self.work_input_path)

    def _apply_stage_namelists(self, stage_name):
        """Apply the stage namelists to the master namelists."""
        namelists = os.listdir(stage_name)

        for namelist in namelists:
            with open(namelist, 'r') as master_nml_f:
                master_namelist = f90nml.read(master_nml_f)

            with open(os.path.join(stage_name, namelist), 'r') as stage_nml_f:
                stage_namelist = f90nml.read(stage_nml_f)

            deep_update(master_namelist, stage_namelist)

            # Write the namelist to the work directory
            master_namelist.write(os.path.join(self.work_input_path, namelist),
                force = True)

    def archive(self):
        """Store model output to laboratory archive and update the
configuration log."""

        # Update the configuration log and save it to the working directory
        completed_stage = self.configuration_log['current_stage']
        self.configuration_log['current_stage'] = ''
        self.configuration_log['completed_stages'].append(completed_stage)

        self.save_configuration_log()

        if int(os.environ['PAYU_N_RUNS']) == 1:
            os.remove('configuration_log.yaml')

        super(StagedCable, self).archive()

    def collate(self):
        pass

    def save_configuration_log(self):
        """Write the updated configuration log back to the staging area."""
        with open('configuration_log.yaml', 'w+') as config_log_f:
            yaml.dump(self.configuration_log, config_log_f)
