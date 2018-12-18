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
import shutil


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
            
    def add_filepath(self, filepath, fullpath, copy=False):
        """
        Bespoke function to add filepath & fullpath to manifest
        object without hashing. Can defer hashing until all files are
        added. Hashing all at once is much faster as overhead for
        threading is spread over all files
        """
        if filepath not in self.data:
            self.data[filepath] = {}

        self.data[filepath]['fullpath'] = fullpath
        self.data[filepath]['hashes'] = {}

        if copy:
            self.data[filepath]['copy'] = copy

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
        
        self.have_exe_manifest = False
        self.have_input_manifest = False
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

    def setup(self):

        # Check if manifest files exist
        self.have_restart_manifest = os.path.exists(self.restart_manifest.path)

        if os.path.exists(self.input_manifest.path) and not self.manifest_config.get('overwrite',False):
            # Read manifest
            print("Loading input manifest: {}".format(self.input_manifest.path))
            self.input_manifest.load()

            if len(self.input_manifest) > 0:
                self.have_input_manifest = True

        if os.path.exists(self.exe_manifest.path):
            # Read manifest
            print("Loading exe manifest: {}".format(self.exe_manifest.path))
            self.exe_manifest.load()

            if len(self.exe_manifest) > 0:
                self.have_exe_manifest = True

        if self.reproduce:

            # Read restart manifest
            print("Loading restart manifest: {}".format(self.restart_manifest.path))
            self.restart_manifest.load()

            # MUST have input and restart manifests to be able to reproduce a run
            if len(self.restart_manifest) > 0:
                self.have_restart_manifest = True
            else:
                raise ValueError("Reproduce is True but restart manifest is empty")
            if not self.have_input_manifest:
                raise ValueError("Reproduce is True but input manifest is empty")
            if self.reproduce_exe and not self.have_exe_manifest:
                raise ValueError("Reproduce is True but executable manifest is empty and reproduce_exe not set to False")

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

            self.have_restart_manifest = False

            # # Generate a restart manifest
            # for model in self.expt.models:
            #     if model.prior_restart_path is not None:
            #         # Try and find a manifest file in the restart dir
            #         restart_mf = PayuManifest.find_manifest(model.prior_restart_path)
            #         if restart_mf is not None:
            #             print("Loading restart manifest: {}".format(os.path.join(model.prior_restart_path,restart_mf.path)))
            #             self.restart_manifest.update(restart_mf,newpath=os.path.join(model.work_init_path_local))
            #             # Have two flags, one per model, the other controls if there is a call
            #             # to make_links in setup()
            #             model.have_restart_manifest = True
            #             # self.have_restart_manifest = True

    def make_links(self):

        self.exe_manifest.make_links()
        self.input_manifest.make_links()
        self.restart_manifest.make_links()

        if not self.reproduce:
            # Add full hash to all existing files. Don't force, will only add if they don't already exist
            print("Add full hashes to input manifest")
            self.input_manifest.add(hashfn=full_hashes)
            print("Writing input manifest")
            self.input_manifest.dump()
            # Add full hash to all existing files. Don't force, will only add if they don't already exist
            print("Add full hashes to restart manifest")
            self.restart_manifest.add(hashfn=full_hashes)
            print("Writing restart manifest")
            self.restart_manifest.dump()

        if not self.reproduce_exe:
            # Add full hash to all existing files. Don't force, will only add if they don't already exist
            print("Add full hashes to exe manifest")
            self.exe_manifest.add(hashfn=full_hashes)
            print("Writing exe manifest")
            self.exe_manifest.dump()

        print("Checking input manifest")
        self.input_manifest.check_fast(reproduce=self.reproduce)

        print("Checking restart manifest")
        self.restart_manifest.check_fast(reproduce=self.reproduce)

        print("Checking exe manifest")
        self.exe_manifest.check_fast(reproduce=self.reproduce_exe)