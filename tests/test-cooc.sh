#!/bin/bash

set -e
set -u

./test-wa.sh
python addcoocrelations.py test-wa-output/*/*.jsonld
