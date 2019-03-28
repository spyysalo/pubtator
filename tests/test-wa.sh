#!/bin/bash

set -e
set -u

SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DATADIR="$SCRIPTDIR/../data"
OUTDIR="$SCRIPTDIR/../data/test-wa-output"
CONVERTER="$SCRIPTDIR/../convertpubtator.py"

INPUT="$DATADIR/samples/bioconcepts2pubtator_offsets.sample"

echo "Clearing $OUTDIR" >&2
rm -rf "$OUTDIR"

echo "Converting $INPUT, output in $OUTDIR" >&2
python3 "$CONVERTER" -f wa-jsonld -o "$OUTDIR" -s -ss "$INPUT"

echo "Done." >&2
