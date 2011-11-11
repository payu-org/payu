# coding: utf-8
"""
The payu implementation of GOLD
"""

from fms import FMS

class gold(FMS):
    #----------------------------
    def __init__(self, **kwargs):
       
        # FMS initalisation
        super(gold, self).__init__()

        # Model-specific configuration
        self.model_name = 'GOLD'
        self.default_exec = 'GOLD'
        self.config_files = ['GOLD_input',
                             'GOLD_override',
                             'diag_table',
                             'input.nml']
        
        self.path_names(**kwargs)
    
    
    #---------------
    def setup(self):
   
        # GOLD-specific initialisation
        if self.counter == 1:
            self.init_config()
       
        # FMS initialisation
        super(gold, self).setup()

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
