# coding: utf-8
"""
GOLD: The payu implementation of GOLD
"""

from payu import Model

class _GOLD(Model):
    def __init__(self):
        self.model_name = 'GOLD'
        self.modules = ['openmpi','ipm']

    def build(self):
        # actual build instructions
        pass

    def run(self):
        # actual run instructions
        pass
