# --- Build a Workflow class to manage the workflow of collate, postscript, sync jobs ---

class Workflow:
    """Class to manage the workflow of run, collate, postscript, sync jobs."""
    
    def __init__(self, workflow_steps, run_number=None):
        self.workflow_steps = workflow_steps
        self.run_number = run_number

    @classmethod
    def read_config(cls, config, run_number=None, skip_step=None):
        """Read the config dictionary and return a dictionary of workflow steps to be executed.
        If skip_step is provided, that step will be skipped in the workflow."""
        workflow_steps = dict()

        if skip_step != 'collate' and config.get('collate', {}).get('enable', True):
            workflow_steps['collate'] = None
        if skip_step != 'postscript' and config.get('postscript', None):
            workflow_steps['postscript'] = None
        if skip_step != 'sync' and config.get('sync', {}).get('enable', False):
            workflow_steps['sync'] = None

        return cls(workflow_steps, run_number)


    def submit_workflow(self, depends_on, config):
        """Submit all later jobs in the workflow in order, passing job IDs as dependencies,
        Update the value in workflow dictionary."""
        fn = self.import_subcommands()

        for step in self.workflow_steps.keys():
            self.workflow_steps[step] = fn[step](self.run_number, depends_on, config)

            # Next step depends on this step's job ID
            depends_on = self.workflow_steps[step]

        return self.workflow_steps

    @staticmethod
    def import_subcommands():
        # Local imports for subcommand job submission
        from payu.subcommands.collate_cmd import submit_collate
        from payu.subcommands.postscript_cmd import submit_postscript
        from payu.subcommands.sync_cmd import submit_sync

        # Build a function lookup dictionary
        return {
            "collate": submit_collate,
            "postscript": submit_postscript,
            "sync": submit_sync
        }
    

    def clean_up(self, failed_step):
        """Clean up any later jobs that depends on the current failed job."""
        # I don't know how to implement this
        pass