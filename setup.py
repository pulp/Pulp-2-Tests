#!/usr/bin/env python3
# coding=utf-8
"""A setuptools-based script for installing Pulp 2 Tests.

For more information, see:

* https://packaging.python.org/en/latest/index.html
* https://docs.python.org/distutils/sourcedist.html
"""
from setuptools import find_packages, setup  # prefer setuptools over distutils


with open('README.rst') as handle:
    LONG_DESCRIPTION = handle.read()


with open('VERSION') as handle:
    VERSION = handle.read().strip()


setup(
    name='pulp-2-tests',
    version=VERSION,
    description='Functional tests for Pulp 2',
    long_description=LONG_DESCRIPTION,
    url='https://github.com/PulpQE/pulp-2-tests',
    author='Jeremy Audet',
    author_email='ichimonji10@gmail.com',
    license='GPLv3',
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        ('License :: OSI Approved :: GNU General Public License v3 or later '
         '(GPLv3+)'),
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    packages=find_packages(include=['pulp_2_tests', 'pulp_2_tests.*']),
    install_requires=[
        'jsonschema',
        'packaging',
        'pulp-smash>=1!0.0.1,<1!1',
        'python-dateutil',
    ],
    extras_require={
        'dev': [
            # For `make lint`
            'flake8',
            'flake8-docstrings',
            'flake8-quotes',
            'pydocstyle',
            'pylint',
            # For `make docs-html` and `make docs-clean`
            'sphinx',
            # For `make package`
            'wheel',
            # For `make publish`
            'twine',
        ],
    },
)
