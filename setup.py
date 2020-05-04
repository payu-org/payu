"""setup.py
   Installation script for payu

   Additional configuration settings are in ``setup.cfg``.
"""

import os
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

PKG_NAME = 'payu'
PKG_VERSION = __import__(PKG_NAME).__version__
PKG_PKGS = [path for (path, dirs, files) in os.walk(PKG_NAME)
            if '__init__.py' in files]

with open('README.rst') as f:
    README_RST = f.read()

setup(
    name=PKG_NAME,
    version=PKG_VERSION,
    description='A climate model workflow manager for supercomputing '
                'environments.',
    long_description=README_RST,
    author='Marshall Ward',
    author_email='python@marshallward.org',
    url='http://github.com/marshallward/payu',

    packages=PKG_PKGS,
    requires=[
        'f90nml',
        'PyYAML',
        'requests',
        'yamanifest',
        'dateutil',
        'tenacity',
    ],
    install_requires=[
        'f90nml >= 0.16',
        'yamanifest >= 0.3.4',
        'PyYAML',
        'requests[security]',
        'python-dateutil',
        'tenacity',
    ],
    tests_require=[
        'pytest',
        'pylint',
        'Sphinx',
    ],
    entry_points={
        'console_scripts': [
            'payu = payu.cli:parse',
            'payu-run = payu.subcommands.run_cmd:runscript',
            'payu-collate = payu.subcommands.collate_cmd:runscript',
            'payu-profile = payu.subcommands.profile_cmd:runscript',
        ]
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Topic :: Utilities',
    ],
    extras_require={
        'mitgcm': ['mnctools>=0.2']
    },
    keywords='{0} supercomputer model climate workflow'.format(PKG_NAME)
)
