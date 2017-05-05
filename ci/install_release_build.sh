#!/bin/bash

# this requires cython to be installed

# this builds the release cleanly
rm -rf dist
git clean -xfd
python setup.py clean
python setup.py cython
python setup.py sdist --formats=gztar
