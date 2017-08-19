#!/bin/bash

set -e
set -u

INPUT="data/samples/bioconcepts2pubtator_offsets.sample"
OUTDIR="test-wa-output"

echo "Clearing $OUTDIR" >&2
rm -rf "$OUTDIR"

echo "Converting $INPUT, output in $OUTDIR" >&2
python convertpubtator.py -f wa-jsonld -o "$OUTDIR" -s "$INPUT"

echo "Done." >&2
