#!/bin/bash

set -e
set -u

SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DATADIR="$SCRIPTDIR/../data"
OUTDIR="$SCRIPTDIR/../data/test-output"
CONVERTER="$SCRIPTDIR/../convertpubtator.py"

# INPUT="data/BioCreative-V-CDR/CDR_TrainingSet.PubTator"
INPUT="$DATADIR/samples/bioconcepts2pubtator_offsets.sample"

echo "Clearing $OUTDIR" >&2
rm -rf "$OUTDIR"
mkdir "$OUTDIR"

echo "Converting $INPUT, output in $OUTDIR" >&2
python "$CONVERTER" -f standoff -o "$OUTDIR" "$INPUT"

echo "Done." >&2
