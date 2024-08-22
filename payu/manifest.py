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

    def calculate_fast(self, previous_manifest):
        """
        Calculate hash value for all filepaths using a fast hash function and
        fall back to slower full hash functions if fast hashes fail to agree,
        with the pre-existing manifest
        """
        # Calculate all fast hashes
        self.add(
            filepaths=self.data.keys(),
            hashfn=self.fast_hashes,
            force=True,
            fullpaths=[self.fullpath(fpath) for fpath
                       in list(self.data.keys())]
        )

        # If fast hashes from previous manifest match, use previous full hashes
        # to avoid re-calculating slow hashes
        self.update_matching_hashes(other=previous_manifest)

        # Search for new files and files with changed fast hashes
        changed_filepaths = set()
        for filepath in self.data.keys():
            for hash in self.data[filepath]['hashes'].values():
                if hash is None:
                    changed_filepaths.add(filepath)

        # Calculate full hashes for these changed filepaths
        if len(changed_filepaths) > 0:
            self.add(
                filepaths=list(changed_filepaths),
                hashfn=self.full_hashes,
                force=True,
                fullpaths=[self.fullpath(fpath) for fpath
                           in list(changed_filepaths)]
            )

    def check_reproduce(self, previous_manifest):
        """
        Compare full hashes with previous manifest
        """
        # Use paths in both manifests to pick up new and missing files
        all_filepaths = set(self.data.keys()).union(
            previous_manifest.data.keys()
        )
        differences = []
        for filepath in all_filepaths:
            for hashfn in self.full_hashes:
                hash = self.get(filepath, hashfn)
                previous_hash = previous_manifest.get(filepath, hashfn)

                if hash is None:
                    differences.append(
                        f"  {filepath}: Missing file (file not in " +
                        "calculated manifest)"
                    )
                elif previous_hash is None:
                    differences.append(
                        f"  {filepath}: New file (file not in stored manifest)"
                    )
                elif hash != previous_hash:
                    differences.append(
                        f"  {filepath}: {hashfn}: {previous_hash} != {hash}"
                    )

        if len(differences) != 0:
            sys.stderr.write(
                f'Run cannot reproduce: manifest {self.path} is not correct\n'
            )
            print(f"Manifest path: stored hash != calculated hash")
            for row in differences:
                print(row)

            sys.exit(1)


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
        self.previous_manifests = {}
        reproduce_config = self.manifest_config.get('reproduce', {})
        self.reproduce = {}
        for mf in ['input', 'restart', 'exe']:
            self.init_mf(mf)
            self.reproduce[mf] = reproduce_config.get(mf, reproduce)

        # Make sure the manifests directory exists
        mkdir_p(os.path.dirname(self.manifests['exe'].path))

    def init_mf(self, mf):
        # Initialise a sub-manifest object
        self.manifests[mf] = PayuManifest(
            os.path.join('manifests', '{}.yaml'.format(mf)),
            ignore=self.ignore,
            fast_hashes=self.fast_hashes,
            full_hashes=self.full_hashes
        )

        # Initialise a sub-manifest object to store pre-existing manifests
        self.previous_manifests[mf] = PayuManifest(
            os.path.join('manifests', '{}.yaml'.format(mf)),
            ignore=self.ignore,
            fast_hashes=self.fast_hashes,
            full_hashes=self.full_hashes
        )

    def __iter__(self):
        """
        Iterator method
        """
        for mf in self.manifests:
            yield self.manifests[mf]

    def __len__(self):
        """Return the number of manifests in the manifest class."""
        return len(self.manifests)

    def load_manifests(self):
        """
        Load pre-existing manifests
        """
        for mf in self.previous_manifests:
            manifest_path = self.previous_manifests[mf].path
            if os.path.exists(manifest_path):
                try:
                    print(f'Loading {mf} manifest: {manifest_path}')
                    self.previous_manifests[mf].load()
                except Exception as e:
                    print(f'Error loading {mf} manifest: {e}')

            # Check manifests are populated when reproduce is configured
            if len(self.previous_manifests[mf]) == 0 and self.reproduce[mf]:
                sys.stderr.write(
                    f'{mf.capitalize()} manifest must exist and be populated '
                    'if reproduce is configured to True\n'
                )
                sys.exit(1)

    def setup(self):
        # Load all available manifests
        self.load_manifests()

    def check_manifests(self):
        print("Checking exe, input and restart manifests")
        for mf in self.manifests:
            # Calculate hashes in manifests
            self.manifests[mf].calculate_fast(self.previous_manifests[mf])

            if self.reproduce[mf]:
                # Compare manifest with previous manifest
                self.manifests[mf].check_reproduce(self.previous_manifests[mf])

        # Update manifests if there's any changes, or create file if empty
        for mf in self.manifests:
            if (self.manifests[mf].data != self.previous_manifests[mf].data
                    or len(self.manifests[mf]) == 0):
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

    def get_all_previous_fullpaths(self):
        """
        Return a list of all fullpaths in manifest files
        """
        files = []
        for mf in self.previous_manifests:
            files.extend(self.previous_manifests[mf].get_fullpaths())
        return files
