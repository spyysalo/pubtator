#!/bin/bash

set -e
set -u

INPUT="data/BioCreative-V-CDR/CDR_TrainingSet.PubTator"
OUTDIR="test-output"

echo "Clearing $OUTDIR" >&2
rm -rf "$OUTDIR"
mkdir "$OUTDIR"

echo "Converting $INPUT, output in $OUTDIR" >&2
./pubtator2standoff.py -o "$OUTDIR" "$INPUT"

echo "Done." >&2
