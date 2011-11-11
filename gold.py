# coding: utf-8
"""
The payu implementation of GOLD
===============================================================================
Primary Contact:    Marshall Ward (marshall.ward@anu.edu.au)
"""

from fms import FMS
import os
import shutil as sh

class gold(FMS):
    #----------------------------
    def __init__(self, **kwargs):
       
        # FMS initalisation
        super(gold, self).__init__()

        # Model-specific configuration
        self.model_name = 'gold'
        self.default_exec = 'GOLD'
        self.config_files = ['GOLD_input',
                             'GOLD_override',
                             'diag_table',
                             'fre_input.nml',
                             'input.nml']
        
        self.path_names(**kwargs)
    
    
    #---------------
    def setup(self):
   
        # FMS initialisation
        super(gold, self).setup()
        
        # GOLD-specific initialisation
        if self.counter == 1:
            self.init_config()
    
    
    #---------------------
    def init_config(self):
        input_filepath = os.path.join(self.work_path, 'input.nml')
        temp_filepath  = ''.join([input_filepath, '~'])
        
        input_file = open(input_filepath)
        temp_file  = open(temp_filepath, 'w')
        
        for line in input_file:
            temp_file.write(line.replace("input_filename = 'r'",
                                         "input_filename = 'n'"))
        
        input_file.close()
        temp_file.close()
        sh.move(temp_filepath, input_filepath)
