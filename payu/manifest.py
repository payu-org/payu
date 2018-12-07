"""payu.manifest
   ===============

   Provides an manifest class to store manifest data, which uses a 
   subclassed yamanifest PayuManifest class

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details.
"""

# Python3 preparation
from __future__ import print_function, absolute_import

# Local
from payu import envmod
from payu.fsops import make_symlink

# External
from yamanifest.manifest import Manifest as YaManifest
import yamanifest as ym
from copy import deepcopy

import os, sys


# fast_hashes = ['nchash','binhash']
fast_hashes = ['binhash']
full_hashes = ['md5']

class PayuManifest(YaManifest):
    """
    A manifest object sub-classed from yamanifest object with some payu specific
    additions and enhancements
    """

    def __init__(self, path, hashes=None, **kwargs):
        super(PayuManifest, self).__init__(path, hashes, **kwargs)

    def check_fast(self, reproduce=False, **args):
        """
        Check hash value for all filepaths using a fast hash function and fall back to slower
        full hash functions if fast hashes fail to agree
        """
        hashvals = {}
        if not self.check_file(filepaths=self.data.keys(),hashvals=hashvals,hashfn=fast_hashes,shortcircuit=True,**args):
            # Run a fast check, if we have failures, deal with them here
            for filepath in hashvals:
                print("Check failed for {} {}".format(filepath,hashvals[filepath]))
                tmphash = {}
                if self.check_file(filepaths=filepath,hashfn=full_hashes,hashvals=tmphash,shortcircuit=False,**args):
                    # File is still ok, so replace fast hashes
                    print("Full hashes ({}) checked ok".format(full_hashes))
                    print("Updating fast hashes for {} in {}".format(filepath,self.path))
                    self.add_fast(filepath,force=True)
                else:
                    # File has changed, update hashes unless reproducing run
                    if not reproduce:
                        print("Updating entry for {} in {}".format(filepath,self.path))
                        self.add_fast(filepath,force=True)
                        self.add(filepath,hashfn=full_hashes,force=True)
                    else:
                        sys.stderr.write("Run cannot reproduce: manifest {} is not correct\n".format(self.path))
                        for fn in full_hashes:
                            sys.stderr.write("Hash {}: manifest: {} file: {}\n".format(fn,self.data[filepath]['hashes'][fn],tmphash[fn]))
                        sys.exit(1)

            # Write updates to version on disk
            self.dump()
            

    def add_fast(self, filepath, hashfn=fast_hashes, force=False):
        """
        Bespoke function to add filepaths but set shortcircuit to True, which means
        only the first calculatable hash will be stored. In this way only one "fast"
        hashing function need be called for each filepath
        """
        self.add(filepath, hashfn, force, shortcircuit=True)
        
    def copy_file(self, filepath):
        """
        Returns flag which says to copy rather than link a file
        """
        copy_file = False
        try:
            copy_file = self.data[filepath]['copy']
        except KeyError:
            return False
        return copy_file

    def make_links(self):
        """
        Payu integration function for creating symlinks in work directories which point
        back to the original file
        """
        print("Making links from manifest: {}".format(self.path))
        for filepath in self:
            # print("Linking {}".format(filepath))
            # Don't try and link to itself, which happens when there is a real
            # file in the work directory, and not a symbolic link
            # if not os.path.realpath(filepath) == self.fullpath(filepath):
            #     make_symlink(self.fullpath(filepath), filepath)
            if self.copy_file(filepath):
                shutil.copy(self.fullpath(filepath), filepath)
            else:
                make_symlink(self.fullpath(filepath), filepath)

class Manifest(object):
    """
    A Manifest class which stores all manifests for file tracking and 
    methods to operate on them 
    """

    def __init__(self, expt, reproduce):

        # Inherit experiment configuration
        self.expt = expt
        self.reproduce = reproduce

        # Manifest control configuration
        self.manifest_config = self.expt.config.get('manifest', {})
        
        self.have_restart_manifest = False

        # If the run sets reproduce, default to reproduce executables. Allow user
        # to specify not to reproduce executables (might not be feasible if
        # executables don't match platform, or desirable if bugs existed in old exe)
        self.reproduce_exe = self.reproduce and self.manifest_config.get('reproduce_exe',True)

        # Not currently supporting specifying hash functions
        # self.hash_functions = manifest_config.get('hashfns', ['nchash','binhash','md5'])

        # Intialise manifests. Can specify the path in config
        self.input_manifest = PayuManifest(self.manifest_config.get('input', 'mf_input.yaml'))
        self.restart_manifest = PayuManifest(self.manifest_config.get('restart', 'mf_restart.yaml'))
        self.exe_manifest = PayuManifest(self.manifest_config.get('exe', 'mf_exe.yaml'))

    # Does it make sense to split this off into a different setup routine when other stuff is defined?
    # def setup(self):

        # Check if manifest files exist
        self.have_input_manifest = os.path.exists(self.input_manifest.path) and not self.manifest_config.get('overwrite',False)
        self.have_restart_manifest = os.path.exists(self.restart_manifest.path)
        self.have_exe_manifest = os.path.exists(self.exe_manifest.path)

        if self.reproduce:
            # MUST have input and restart manifests to be able to reproduce a run
            assert(self.have_input_manifest)
            assert(self.have_restart_manifest)
            if self.reproduce_exe:
                assert(self.have_exe_manifest)
        else:
            # Only use a restart manifest when reproducing a run, otherwise always generare a new one
            self.have_restart_manifest = False

        if self.have_input_manifest:
            # Read manifest
            print("Loading input manifest: {}".format(self.input_manifest.path))
            self.input_manifest.load()

            if len(self.input_manifest) == 0:
                if self.reproduce:
                    raise ValueError('Input manifest is empty, but reproduce is true')
                # if manifest is empty revert flag to ensure input directories are used
                self.have_input_manifest = False

        if self.have_exe_manifest and self.reproduce_exe:
            # Read manifest
            print("Loading exe manifest: {}".format(self.exe_manifest.path))
            self.exe_manifest.load()

            if len(self.exe_manifest) == 0:
                if self.reproduce:
                    raise ValueError('Exe manifest is empty, but reproduce and reproduce_exe is true')
                # if manifest is empty revert flag to ensure input directories are used
                self.have_exe_manifest = False
        else:
            self.have_exe_manifest = False

        if self.reproduce:
            # Read restart manifest
            print("Loading restart manifest: {}".format(self.restart_manifest.path))
            self.restart_manifest.load()

            # Restart manifest must be populated for a reproducible run
            assert(len(self.input_manifest) > 0)

            for model in self.expt.models:
                model.have_restart_manifest = True

            # If the run counter is zero inspect the restart manifest for an appropriate
            # value
            for filepath in self.restart_manifest:
                head = os.path.dirname(self.restart_manifest.fullpath(filepath))
                # Inspect each element of the fullpath looking for restartxxx style
                # directories. Exit 
                while true:
                    head, tail = os.path.split(head)
                    if tail.startswith('restart'):
                        try:
                            n = int(tail.lstrip('restart'))
                        except ValueError:
                            pass
                        else:
                            self.counter = n + 1
                            break
                            
                # Short circuit as soon as restart dir found
                if self.expt.counter == 0: break
                            
        else:

            # Generate a restart manifest
            for model in self.expt.models:
                if model.prior_restart_path is not None:
                    # Try and find a manifest file in the restart dir
                    restart_mf = PayuManifest.find_manifest(model.prior_restart_path)
                    if restart_mf is not None:
                        print("Loading restart manifest: {}".format(os.path.join(model.prior_restart_path,restart_mf.path)))
                        self.restart_manifest.update(restart_mf,newpath=os.path.join(model.work_init_path_local))
                        # Have two flags, one per model, the other controls if there is a call
                        # to make_links in setup()
                        model.have_restart_manifest = True
                        # self.have_restart_manifest = True
