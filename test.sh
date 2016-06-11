#!/bin/bash

set -e
set -u

# INPUT="data/BioCreative-V-CDR/CDR_TrainingSet.PubTator"
INPUT="data/samples/bioconcepts2pubtator_offsets.sample"
OUTDIR="test-output"

echo "Clearing $OUTDIR" >&2
rm -rf "$OUTDIR"
mkdir "$OUTDIR"

echo "Converting $INPUT, output in $OUTDIR" >&2
python convertpubtator.py -f standoff -o "$OUTDIR" "$INPUT"

echo "Done." >&2
