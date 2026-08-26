# --- Build a Workflow class to manage the workflow of collate, postscript, sync jobs ---

class Workflow:
    """Class to manage the workflow of run, collate, postscript, sync jobs."""
    
    def __init__(self, config, run_number=None):
        self.run_number = run_number
        self.config = config


    def build_workflow(self):
        """Build the workflow for the current experiment, e.g.,
        {"collate": None, "postscript": None, "sync": None}. 
        The value will be updated as job id when available"""
        self.workflow_steps = dict()
        if self.config.get('collate', {}).get('enable', True):
            self.workflow_steps['collate'] = None
        if self.config.get('postscript', None):
            self.workflow_steps['postscript'] = None
        if self.config.get('sync', {}).get('enable', False):
            self.workflow_steps['sync'] = None


    def submit_workflow(self, depends_on):
        """Submit all later jobs in the workflow in order, passing job IDs as dependencies,
        Update the value in workflow dictionary."""
        fn = self.import_subcommands()

        for step in self.workflow_steps.keys():
            self.workflow_steps[step] = fn[step](self.run_number, depends_on, self.config)

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