# coding: utf-8
"""
Payu: A generic driver for numerical models on the NCI computing cluster (vayu)
-------------------------------------------------------------------------------
Primary Contact:    Marshall Ward (marshall.ward@anu.edu.au)
"""

import os

class Experiment(object):
    """Abstraction of a particular experiment on vayu"""
    # Many methods are taken, then patched, from the model

    def __init__(self, model, *args, **kwargs):
        self.model = model
        
        # Get these somehow
        self.modules = model.modules


class Model(object):
    """Abstraction of numerical models on vayu"""
    # Most of these methods are defined by individual models (polymorphism)
    
    def __init__(self, *args, **kwargs):
        self.model_name = None
    
    def build(self):
        raise NotImplementedError('Subclass must implement build automation.')
    
    def run(self):
        raise NotImplementedError('Subclass much implement model execution.')
