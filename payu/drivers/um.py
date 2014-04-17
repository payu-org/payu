# coding: utf-8
"""
The payu interface for the UM atmosphere model
-------------------------------------------------------------------------------
Contact: Marshall Ward <marshall.ward@anu.edu.au>
-------------------------------------------------------------------------------
Distributed as part of Payu, Copyright 2011 Marshall Ward
Licensed under the Apache License, Version 2.0
http://www.apache.org/licenses/LICENSE-2.0
"""

from payu.modeldriver import Model


class UnifiedModel(Model):

    #---
    def __init__(self, expt, name, config):
        super(UnifiedModel, self).__init__(expt, name, config)

        self.model_type = 'um'
        self.default_exec = 'um'

        self.modules = ['pbs',
                        'openmpi']


    #---
    def archive(self):
        raise NotImplementedError

    def set_model_pathnames(self):
        super(UnifiedModel, self).set_model_pathnames()

        ice_nml_path = os.path.join(self.control_path, self.ice_nml_fname)
        self.ice_nmls = f90nml.read(ice_nml_path)

        res_path = os.path.normpath(setup_nml['restart_dir'])
        if not os.path.isabs(res_path):
            res_path = os.path.join(self.work_path, res_path)

        self.work_init_path = res_path
        self.work_restart_path = res_path

        work_out_path = os.path.normpath(setup_nml['history_dir'])
        if not os.path.isabs(work_out_path):
            work_out_path = os.path.join(self.work_path, work_out_path)

        self.work_output_path = work_out_path

        # Determine if there is a work input path
        grid_nml = self.ice_nmls['grid_nml']
        input_path, grid_fname = os.path.split(grid_nml['grid_file'])
        if input_path and not input_path == '.':
            assert not os.path.isabs(input_path)


        self.work_input_path = os.path.join(self.work_path, input_path)


    #---
    def set_model_output_paths(self):
        super(UnifiedModel, self).set_model_output_paths()

        res_dir = self.ice_nmls['setup_nml']['restart_dir']

        # Use the local initialization restarts if present
        # TODO: Check for multiple res_paths across input paths?
        if self.expt.counter == 0:
            for input_path in self.input_paths:
                if os.path.isabs(res_dir):
                    init_res_path = res_dir
                else:
                    init_res_path = os.path.join(input_path, res_dir)
                if os.path.isdir(init_res_path):
                    self.prior_restart_path = init_res_path


    #---
    def get_prior_restart_files(self):
        return [f for f in os.listdir(self.prior_restart_path)
                if f.startswith('iced.')]

    #---
    def collate(self):
        raise NotImplementedError

    #---
    def setup(self):
        super(UnifiedModel, self).setup()

        if self.expt.counter > 0:

            # Update input namelist
            setup_nml = self.ice_nmls['setup_nml']

            setup_nml['runtype'] = 'continue'
            setup_nml['restart'] = True

            nml_path = os.path.join(self.work_path, self.ice_nml_fname)
            f90nml.write(self.ice_nmls, nml_path + '~')
            shutil.move(nml_path + '~', nml_path)

            # Generate ice.restart_file
            # TODO: Check the filenames more aggressively
            last_restart_file = sorted(self.get_prior_restart_files())[-1]

            res_ptr_path = os.path.join(self.work_init_path, 'ice.restart_file')
            with open(res_ptr_path, 'w') as res_ptr:
                print(last_restart_file, file=res_ptr)


    #---
    def archive(self, **kwargs):

        for f in os.listdir(self.work_input_path):
            f_path = os.path.join(self.work_input_path, f)
            if os.path.islink(f_path):
                os.remove(f_path)

        # Archive restart files before processing model output
        cmd = 'mv {src} {dst}'.format(src=self.work_restart_path,
                                      dst=self.restart_path)
        rc = sp.Popen(shlex.split(cmd)).wait()
        assert rc == 0

