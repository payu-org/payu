# coding: utf-8
"""
The payu implementation of MOM4
"""

from fms import FMS

class mom4(FMS):
    #----------------------------
    def __init__(self, **kwargs):
        
        # FMS initalisation
        super(mom4, self).__init__(**kwargs)
       
        

        # Model-specific configuration
        self.model_name = 'mom4'
        self.default_exec = 'mom4'
        self.config_files = ['data_table',
                             'diag_table',
                             'field_table',
                             'input.nml']
        
        self.path_names(**kwargs)
