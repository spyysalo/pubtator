#!/bin/bash

set -e
set -u

SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
IDMAP="$SCRIPTDIR/../data/samples/NCBIGENE-PRO-idmapping.dat"
DATADIR="$SCRIPTDIR/../data/test-wa-output"

"$SCRIPTDIR/test-wa.sh"
#python "$SCRIPTDIR/../tools/mapids.py" -v "$IDMAP" "$DATADIR"/*/*.jsonld
python "$SCRIPTDIR/../tools/mapids.py" -v -r "$IDMAP" "$DATADIR"
