import os
from setuptools import setup, find_packages

payu_version = __import__('payu').__version__
payu_scripts = [os.path.join('payu/bin', f) for f in os.listdir('payu/bin')]

with open('README.rst') as f:
    readme_rst = f.read()

setup(
    name = 'payu',
    version = payu_version,
    description = 'A climate model workflow manager for supercomputing '
                  'environments.',
    long_description = readme_rst,
    author = 'Marshall Ward',
    author_email = 'python@marshallward.org',
    url = 'http://github.com/marshallward/payu',

    packages = find_packages(),
    install_requires = ['f90nml', 'PyYAML'],
    scripts = payu_scripts,

    classifiers = [
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Topic :: Utilities',
    ],

    keywords = 'payu supercomputer model climate workflow'
)
