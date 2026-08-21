# --- Work in progress: build a workflow class ---
# Local imports for subcommand job submission
from payu.telemetry import get_job_file_path_with_id
import json

class Workflow:
    """Class to manage the workflow of run, collate, postscript, sync jobs."""
    
    def __init__(self, config, run_number=None):
        self.run_number = run_number
        self.config = config


    def build_workflow(self, postscript):
        """Build the workflow for the current experiment, e.g.,
        {"collate": None, "postscript": None, "sync": None}. 
        The value will be updated as job id when available"""
        self.workflow_steps = dict()
        if self.config.get('collate', {}).get('enable', True):
            self.workflow_steps['collate'] = None
        if postscript:
            self.workflow_steps['postscript'] = None
        if self.config.get('sync', {}).get('enable', False):
            self.workflow_steps['sync'] = None


    def submit_workflow(self, depends_on):
        """Submit all later jobs in the workflow in order, passing job IDs as dependencies,
        Update the value in workflow dictionary."""
        for step in self.workflow_steps.keys():
            if step == "collate":
                from payu.subcommands.collate_cmd import submit_collate
                depends_on = submit_collate(self.run_number, depends_on)

            elif step == "postscript":
                from payu.subcommands.postscript_cmd import submit_postscript
                depends_on = submit_postscript(self.run_number, depends_on)

            elif step == "sync":
                from payu.subcommands.sync_cmd import submit_sync
                depends_on = submit_sync(self.run_number, depends_on, self.config)

            else:
                raise ValueError(f"Unknown workflow step: {step}")

            self.workflow_steps[step] = depends_on

        return self.workflow_steps


    def clean_up(self, failed_step):
        """Clean up any later jobs that depends on the current failed job."""
        # I don't know how to implement this
        pass