#!/bin/bash

set -e
set -u

SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DATADIR="$SCRIPTDIR/../data"

"$SCRIPTDIR/test-wa.sh"
python3 "$SCRIPTDIR/../tools/getmappings.py" -r "$DATADIR"/test-wa-output/*
