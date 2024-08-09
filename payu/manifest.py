"""payu.manifest
   ===============

   Provides an manifest class to store manifest data, which uses a
   subclassed yamanifest PayuManifest class

   :copyright: Copyright 2019 Aidan Heerdegen, see AUTHORS for details.
   :license: Apache License, Version 2.0, see LICENSE for details.
"""
from __future__ import print_function, absolute_import

# External
import fnmatch
import os
import sys
import shutil
import stat

from yamanifest.manifest import Manifest as YaManifest

from payu.fsops import make_symlink, mkdir_p


# fast_hashes = ['nchash','binhash']
fast_hashes = ['binhash']
full_hashes = ['md5']
all_hashes = fast_hashes + full_hashes


class PayuManifest(YaManifest):
    """
    A manifest object sub-classed from yamanifest object with some payu
    specific additions and enhancements.
    """
    def __init__(self, path,
                 ignore=None,
                 fast_hashes=fast_hashes,
                 full_hashes=full_hashes,
                 **kwargs):

        super(PayuManifest, self).__init__(path=path,
                                           hashes=fast_hashes+full_hashes,
                                           **kwargs)
        self.fast_hashes = fast_hashes
        self.full_hashes = full_hashes

        if ignore is not None:
            self.ignore = ignore

        self.needsync = False

        self.previous_filepaths = set()

    def set_previous_filepaths(self):
        """
        Save previous filepaths information - this is obtained from the
        pre-existing manifests. This is used to keep track of changes to
        the manifest.
        """
        self.previous_filepaths = set(self.data.keys())

    def check_fast(self, reproduce=False, **args):
        """
        Check hash value for all filepaths using a fast hash function and fall
        back to slower full hash functions if fast hashes fail to agree.
        """
        hashvals = {}

        fast_check = self.check_file(
            filepaths=self.data.keys(),
            hashvals=hashvals,
            hashfn=self.fast_hashes,
            shortcircuit=True,
            **args
        )

        if not fast_check:

            # Save all the fast hashes for failed files that we've already
            # calculated
            for filepath in hashvals:
                for hash, val in hashvals[filepath].items():
                    self.data[filepath]['hashes'][hash] = val

            if reproduce:
                for filepath in hashvals:
                    print('Check failed for {0} {1}'
                          ''.format(filepath, hashvals[filepath]))
                    tmphash = {}
                    full_check = self.check_file(
                        filepaths=filepath,
                        hashfn=self.full_hashes,
                        hashvals=tmphash,
                        shortcircuit=False,
                        **args
                    )

                    if full_check:
                        # File is still ok, so replace fast hashes
                        print('Full hashes ({0}) checked ok'
                              ''.format(self.full_hashes))
                        print('Updating fast hashes for {0} in {1}'
                              ''.format(filepath, self.path))
                        self.add_fast(filepath, force=True)
                        print('Saving updated manifest')
                        self.needsync = True
                    else:
                        sys.stderr.write(
                            'Run cannot reproduce: manifest {0} is not '
                            'correct\n'.format(self.path)
                        )
                        for path, hashdict in tmphash.items():
                            print('    {0}:'.format(path))
                            for hash, val in hashdict.items():
                                hash_table = self.data[path]['hashes']
                                hash_table_val = hash_table.get(hash, None)
                                print('        {0}: {1} != {2}'
                                      ''.format(hash, val, hash_table_val))
                        sys.exit(1)
            else:
                # Not relevant if full hashes are correct. Regenerate full
                # hashes for all filepaths that failed fast check.
                print('Updating full hashes for {0} files in {1}'
                      ''.format(len(hashvals), self.path))

                # Add all full hashes at once -- much faster. Definitely want
                # to force the full hash to be updated. In the specific case of
                # an empty hash the value will be None, without force it will
                # be written as null.
                self.add(
                    filepaths=list(hashvals.keys()),
                    hashfn=self.full_hashes,
                    force=True,
                    fullpaths=[self.fullpath(fpath) for fpath
                               in list(hashvals.keys())]
                )

                # Flag need to update version on disk
                self.needsync = True

        # Check for any missing files
        if reproduce and len(self.previous_filepaths) > 0:
            sys.stderr.write(
                f"Run cannot reproduce: Files in {self.path} " +
                "are no longer in work directory:\n  - " +
                "\n  - ".join(self.previous_filepaths) + '\n'
            )
            exit(1)

    def add_filepath(self, filepath, fullpath, hashes, copy=False):
        """
        Bespoke function to add filepath & fullpath to manifest
        object without hashing. Can defer hashing until all files are
        added. Hashing all at once is much faster as overhead for
        threading is spread over all files
        """

        # Ignore directories
        if os.path.isdir(fullpath):
            return False

        # Ignore anything matching the ignore patterns
        for pattern in self.ignore:
            if fnmatch.fnmatch(os.path.basename(fullpath), pattern):
                return False

        if filepath not in self.data:
            self.data[filepath] = {}

        self.data[filepath]['fullpath'] = fullpath
        if 'hashes' not in self.data[filepath]:
            self.data[filepath]['hashes'] = {hash: None for hash in hashes}

        if copy:
            self.data[filepath]['copy'] = copy

        if filepath in self.previous_filepaths:
            self.previous_filepaths.remove(filepath)

        return True

    def add_fast(self, filepath, hashfn=None, force=False):
        """
        Bespoke function to add filepaths but set shortcircuit to True, which
        means only the first calculable hash will be stored. In this way only
        one "fast" hashing function need be called for each filepath.
        """
        if hashfn is None:
            hashfn = self.fast_hashes
        self.add(filepath, hashfn, force, shortcircuit=True)

    def copy_file(self, filepath):
        """
        Returns flag which says to copy rather than link a file.
        """
        copy_file = False
        try:
            copy_file = self.data[filepath]['copy']
        except KeyError:
            return False
        return copy_file

    def make_link(self, filepath):
        """
        Payu integration function for creating symlinks in work directories
        which point back to the original file.
        """
        if not os.path.exists(self.fullpath(filepath)):
            raise FileNotFoundError(
                "Unable to create symlink in work directory. "
                f"File not found: {self.fullpath(filepath)}"
            )
        else:
            try:
                destdir = os.path.dirname(filepath)
                # Make destination directory if not already exists
                # Necessary because sometimes this is called before
                # individual model setup
                if not os.path.exists(destdir):
                    os.makedirs(destdir)
                if self.copy_file(filepath):
                    shutil.copy(self.fullpath(filepath), filepath)
                    perm = (stat.S_IRUSR | stat.S_IRGRP
                            | stat.S_IROTH | stat.S_IWUSR)
                    os.chmod(filepath, perm)
                else:
                    make_symlink(self.fullpath(filepath), filepath)
            except Exception:
                action = 'copying' if self.copy_file else 'linking'
                print('payu: error: {action} orig: {orig} '
                      'local: {local}'.format(action=action,
                                              orig=self.fullpath(filepath),
                                              local=filepath))
                raise
            finally:
                self.previous_filepaths.discard(filepath)

    def make_links(self):
        """
        Used to make all links at once for scaninputs=False
        """
        for filepath in list(self):
            if os.path.exists(self.fullpath(filepath)):
                self.make_link(filepath)

    def copy(self, path):
        """
        Copy myself to another location
        """
        shutil.copy(self.path, path)

    def get_fullpaths(self):
        files = []
        for filepath in list(self):
            files.append(self.fullpath(filepath))
        return files

    def get_hashes(self, hashfn):
        hashes = []
        for filepath in self:
            hashes.append(self.get(filepath, hashfn))
        return hashes


class Manifest(object):
    """
    A Manifest class which stores all manifests for file tracking and
    methods to operate on them
    """

    def __init__(self, config, reproduce):

        # Manifest control configuration
        self.manifest_config = config

        # Not currently supporting specifying hash functions
        self.fast_hashes = self.manifest_config.get('fasthash', fast_hashes)
        self.full_hashes = self.manifest_config.get('fullhash', full_hashes)

        if type(self.fast_hashes) is str:
            self.fast_hashes = [self.fast_hashes, ]
        if type(self.full_hashes) is str:
            self.full_hashes = [self.full_hashes, ]

        self.ignore = self.manifest_config.get('ignore', ['.*'])
        if isinstance(self.ignore, str):
            self.ignore = [self.ignore]

        # Initialise manifests and reproduce flags
        self.manifests = {}
        self.have_manifest = {}
        reproduce_config = self.manifest_config.get('reproduce', {})
        self.reproduce = {}
        for mf in ['input', 'restart', 'exe']:
            self.init_mf(mf)
            self.reproduce[mf] = reproduce_config.get(mf, reproduce)

        # Make sure the manifests directory exists
        mkdir_p(os.path.dirname(self.manifests['exe'].path))

        # Set flag to auto-scan input directories
        self.scaninputs = self.manifest_config.get('scaninputs', True)

        # Ensure configured input files are discovered when reproduce is True
        if self.reproduce['input'] and not self.scaninputs:
            print("scaninputs set to True when reproduce input is True")
            self.scaninputs = True

    def init_mf(self, mf):
        # Initialise a sub-manifest object
        self.manifests[mf] = PayuManifest(
            os.path.join('manifests', '{}.yaml'.format(mf)),
            ignore=self.ignore,
            fast_hashes=self.fast_hashes,
            full_hashes=self.full_hashes
        )
        self.have_manifest[mf] = False

    def __iter__(self):
        """
        Iterator method
        """
        for mf in self.manifests:
            yield self.manifests[mf]

    def __len__(self):
        """Return the number of manifests in the manifest class."""
        return len(self.manifests)

    def load(self):
        """
        Load manifests
        """
        for mf in self.manifests:
            self.have_manifest[mf] = False
            if (os.path.exists(self.manifests[mf].path)):
                try:
                    print('Loading {mf} manifest: {path}'
                          ''.format(mf=mf, path=self.manifests[mf].path))
                    self.manifests[mf].load()
                except Exception as e:
                    print('Error loading {mf} manifest: '
                          '{error}'.format(mf=mf, error=e))
                finally:
                    if len(self.manifests[mf]) > 0:
                        self.have_manifest[mf] = True

            # Check manifests are populated when reproduce is configured
            if not self.have_manifest[mf] and self.reproduce[mf]:
                sys.stderr.write(
                    f'{mf.capitalize()} manifest must exist and be populated '
                    'if reproduce is configured to True\n'
                )
                sys.exit(1)

    def set_previous_filepaths(self):
        """
        Save the existing filepath infomation to each manifest
        """
        for mf in self.manifests.keys():
            if self.have_manifest[mf]:
                self.manifests[mf].set_previous_filepaths()

    def setup(self):

        # Load all available manifests
        self.load()

        # Save existing filepaths infomation in each manifest
        self.set_previous_filepaths()

        if self.have_manifest['exe'] and not self.reproduce['exe']:
            # Re-initialise exe manifest. Trivial to recreate
            # and means no check required for changed executable
            # paths
            self.init_mf('exe')

        if self.have_manifest['restart'] and not self.reproduce['restart']:
            # Re-initialise restart manifest. Only keep restart manifest
            # if reproduce. Normally want to scan for new restarts
            self.init_mf('restart')

        # Make links in work directory for existing input manifest
        # when scan inputs is set to False
        if self.have_manifest['input'] and not self.scaninputs:
            print('Making input symlinks using the existing manifest')
            self.manifests['input'].make_links()

    def check_manifests(self):

        print("Checking exe and input manifests")
        self.manifests['exe'].check_fast(reproduce=self.reproduce['exe'])

        if not self.reproduce['input']:
            if len(self.manifests['input'].previous_filepaths) > 0:
                # Delete missing filepaths from input manifest
                for filepath in self.manifests['input'].previous_filepaths:
                    print('File no longer in input directory: {file} '
                          'removing from manifest'.format(file=filepath))
                    self.manifests['input'].delete(filepath)
                self.manifests['input'].needsync = True

        self.manifests['input'].check_fast(reproduce=self.reproduce['input'])

        if self.reproduce['restart']:
            print("Checking restart manifest")
        else:
            print("Creating restart manifest")
            self.manifests['restart'].needsync = True
        self.manifests['restart'].check_fast(
                reproduce=self.reproduce['restart'])

        # Write updates to version on disk
        for mf in self.manifests:
            if self.manifests[mf].needsync:
                print("Writing {}".format(self.manifests[mf].path))
                self.manifests[mf].dump()

    def copy_manifests(self, path):

        mkdir_p(path)
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
        filepath = os.path.normpath(filepath)
        if self.manifests[manifest].add_filepath(
                filepath=filepath,
                fullpath=fullpath,
                hashes=self.fast_hashes + self.full_hashes,
                copy=copy):
            # Only link if filepath was added
            self.manifests[manifest].make_link(filepath)

    def get_all_fullpaths(self):
        """
        Return a list of all fullpaths in manifest files
        """
        files = []
        for mf in self.manifests:
            files.extend(self.manifests[mf].get_fullpaths())
        return files
