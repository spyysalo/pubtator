#!/bin/bash

set -e
set -u

./test-wa.sh
python getmappings.py -r test-wa-output/*
