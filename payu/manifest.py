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
from payu.fsops import make_symlink, get_git_revision_hash, is_ancestor

# External
from yamanifest.manifest import Manifest as YaManifest
import yamanifest as ym
from copy import deepcopy

import os, sys, fnmatch
import shutil
from distutils.dir_util import mkpath


# fast_hashes = ['nchash','binhash']
fast_hashes = ['binhash']
full_hashes = ['md5']
all_hashes = fast_hashes + full_hashes

class PayuManifest(YaManifest):
    """
    A manifest object sub-classed from yamanifest object with some payu specific
    additions and enhancements
    """

    def __init__(self, path, hashes=None, ignore=None, **kwargs):
        super(PayuManifest, self).__init__(path, hashes, **kwargs)

        if ignore is not None:
            self.ignore = ignore

        self.header['git_commit_id'] = None
        self.needsync = False

    def check_fast(self, reproduce=False, **args):
        """
        Check hash value for all filepaths using a fast hash function and fall back to slower
        full hash functions if fast hashes fail to agree
        """
        hashvals = {}
        # Run a fast check
        if not self.check_file(filepaths=self.data.keys(),hashvals=hashvals,hashfn=fast_hashes,shortcircuit=True,**args):

            # Save all the fast hashes for failed files that we've already calculated
            for filepath in hashvals:
                for hash, val in hashvals[filepath].items():
                    self.data[filepath]["hashes"][hash] = val

            if reproduce:
                for filepath in hashvals:
                    print("Check failed for {} {}".format(filepath,hashvals[filepath]))
                    tmphash = {}
                    if self.check_file(filepaths=filepath,hashfn=full_hashes,hashvals=tmphash,shortcircuit=False,**args):
                        # File is still ok, so replace fast hashes
                        print("Full hashes ({}) checked ok".format(full_hashes))
                        print("Updating fast hashes for {} in {}".format(filepath,self.path))
                        self.add_fast(filepath,force=True)
                        print("Saving updated manifest")
                        self.needsync = True
                    else:
                        sys.stderr.write("Run cannot reproduce: manifest {} is not correct\n".format(self.path))
                        for path, hashdict in tmphash.items():
                            print("    {}:".format(path))
                            for hash, val in hashdict.items():
                                print("        {}: {} != {}".format(hash,val,self.data[path]['hashes'].get(hash,None)))
                        sys.exit(1)
            else:
                # Not relevant if full hashes are correct. Regenerate full hashes for all 
                # filepaths that failed fast check
                print("Updating full hashes for {} files in {}".format(len(hashvals),self.path))

                # Add all full hashes at once -- much faster. Definitely want to force
                # the full hash to be updated. In the specific case of an empty hash the 
                # value will be None, without force it will be written as null
                self.add(filepaths=list(hashvals.keys()),hashfn=full_hashes,force=True)

                # Flag need to update version on disk
                self.needsync = True
    def git_id(self, id=None):
        """
        Return and optionally set the git commit id (hash) in the header of the manifest file
        """
        if id is not None:
            self.header['git_commit_id'] = id
        return self.header['git_commit_id']
            
    def dump(self):
        """
        Add git hash to header before dumping the file
        """
        self.git_id(id=get_git_revision_hash())
        super(PayuManifest, self).dump()

    def add_filepath(self, filepath, fullpath, copy=False):
        """
        Bespoke function to add filepath & fullpath to manifest
        object without hashing. Can defer hashing until all files are
        added. Hashing all at once is much faster as overhead for
        threading is spread over all files
        """

        # Ignore directories
        if os.path.isdir(fullpath):
            return
        
        # Ignore anything matching the ignore patterns
        for pattern in self.ignore:
            if fnmatch.fnmatch(os.path.basename(fullpath), pattern):
                return

        if filepath not in self.data:
            self.data[filepath] = {}

        self.data[filepath]['fullpath'] = fullpath
        if 'hashes' not in self.data[filepath]:
            self.data[filepath]['hashes'] = {hash: None for hash in all_hashes}

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
        delete_list = []
        for filepath in self:
            # Check file exists. It may have been deleted but still in manifest
            if not os.path.exists(self.fullpath(filepath)):
                delete_list.append(filepath)
                continue

            if self.copy_file(filepath):
                shutil.copy(self.fullpath(filepath), filepath)
            else:
                make_symlink(self.fullpath(filepath), filepath)

        for filepath in delete_list:
            print("File not found: {} removing from manifest".format(self.fullpath(filepath)))
            self.delete(filepath)
            self.needsync = True

    def copy(self, path):
        """
        Copy myself to another location
        """
        shutil.copy(self.path, path)

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
        
        # If the run sets reproduce, default to reproduce executables. Allow user
        # to specify not to reproduce executables (might not be feasible if
        # executables don't match platform, or desirable if bugs existed in old exe)
        self.reproduce_exe = self.reproduce and self.manifest_config.get('reproduce_exe',True)

        # Not currently supporting specifying hash functions
        # self.hash_functions = manifest_config.get('hashfns', ['nchash','binhash','md5'])

        self.ignore = self.manifest_config.get('ignore',['.*'])
        self.ignore = [self.ignore] if isinstance(self.ignore, str) else self.ignore

        # Intialise manifests
        self.manifests = {}
        for mf in ['input', 'restart', 'exe']:
            self.manifests[mf] = PayuManifest(os.path.join('manifests','{}.yaml'.format(mf)), ignore=self.ignore)

        self.have_manifest = {}
        for mf in self.manifests:
            self.have_manifest[mf] = False

        # Make sure the manifests directory exists
        mkpath(os.path.dirname(self.manifests['exe'].path))

    def __iter__(self):
        """
        Iterator method
        """
        for mf in self.manifests:
            yield self.manifests[mf]

    def __len__(self):
        """
        Return the number of manifests in the manifest class
        """
        return len(self.manifests)

    def setup(self):

        # Check if manifest files exist
        self.have_manifest['restart'] = os.path.exists(self.manifests['restart'].path)

        if os.path.exists(self.manifests['input'].path) and not self.manifest_config.get('overwrite',False):
            # Read manifest
            print("Loading input manifest: {}".format(self.manifests['input'].path))
            self.manifests['input'].load()

            if len(self.manifests['input']) > 0:
                self.have_manifest['input'] = True

            if self.have_manifest['input']:
                # Warn if config has changed since input manifest was created.
                # TODO: check input field in the YaML file has changed since
                ret = is_ancestor(self.expt.config['git_commit_id'], self.manifests['input'].git_id())
                # is_ancestor will return None if there is no git repo, so allow for this case
                if ret is not None and not ret:
                    print("\nWARNING! Config file has been altered since input manifest was generated.") 
                    print("If input paths have changed delete manifests/input.yaml to rescan input directories\n") 

        if os.path.exists(self.manifests['exe'].path):
            # Read manifest
            print("Loading exe manifest: {}".format(self.manifests['exe'].path))
            self.manifests['exe'].load()

            if len(self.manifests['exe']) > 0:
                self.have_manifest['exe'] = True

        if self.reproduce:

            # Read restart manifest
            print("Loading restart manifest: {}".format(self.have_manifest['restart']))
            self.manifests['restart'].load()

            if len(self.manifests['restart']) > 0:
                self.have_manifest['restart'] = True

            # MUST have input and restart manifests to be able to reproduce a run
            for mf in ['restart', 'input']:
                if not self.have_manifest[mf]:
                    print("{} manifest cannot be empty if reproduce is True".format(mf.capitalize()))
                    exit(1)

            if self.reproduce_exe and not self.have_manifest['exe']:
                print("Executable manifest cannot empty if reproduce and reproduce_exe are True")
                exit(1)

            for model in self.expt.models:
                model.have_restart_manifest = True

            # Inspect the restart manifest for an appropriate value of # experiment 
            # counter if not specified on the command line (and this env var set)
            if not os.environ.get('PAYU_CURRENT_RUN'):
                for filepath in self.manifests['restart']:
                    head = os.path.dirname(self.manifests['restart'].fullpath(filepath))
                    # Inspect each element of the fullpath looking for restartxxx style
                    # directories. Exit 
                    while True:
                        head, tail = os.path.split(head)
                        if tail.startswith('restart'):
                            try:
                                n = int(tail.lstrip('restart'))
                            except ValueError:
                                pass
                            else:
                                self.expt.counter = n + 1
                                break
                                
                    # Short circuit as soon as restart dir found
                    if self.expt.counter == 0: break 
                            
        else:

            self.have_manifest['restart'] = False

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

        print("Making links from manifests")

        for mf in self.manifests:
            self.manifests[mf].make_links()

        print("Checking exe and input manifests")
        self.manifests['exe'].check_fast(reproduce=self.reproduce_exe)
        self.manifests['input'].check_fast(reproduce=self.reproduce)

        if self.reproduce:
            print("Checking restart manifest")
        else:
            print("Creating restart manifest")
        self.manifests['restart'].check_fast(reproduce=self.reproduce)

        # Write updates to version on disk
        for mf in self.manifests:
            if self.manifests[mf].needsync:
                print("Writing {}".format(self.manifests[mf].path))
                self.manifests[mf].dump()

    def copy_manifests(self, path):

        mkpath(path)
        try:
            for mf in self.manifests:
                self.manifests[mf].copy(path)
        except IOError:
            pass

    def add_filepath(self, manifest, filepath, fullpath, copy=False):
        """
        Wrapper to the add_filepath function in PayuManifest. Prevents outside
        code from directly calling anything in PayuManifest.
        """
        self.manifests[manifest].add_filepath(filepath, fullpath, copy)
