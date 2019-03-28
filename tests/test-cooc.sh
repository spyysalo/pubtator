#!/bin/bash

set -e
set -u

SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DATADIR="$SCRIPTDIR/../data/test-wa-output"

"$SCRIPTDIR/test-wa.sh"
python3 "$SCRIPTDIR/../tools/addcoocrelations.py" -r "$DATADIR"
