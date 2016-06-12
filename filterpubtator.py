#!/usr/bin/env python

# Filter PubTator data to lines starting with given IDs.

from __future__ import print_function

import sys
import re

ID_RE = re.compile(r'^(\d+)')

def argparser():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('idlist', metavar='IDFILE',
                    help='List of IDs to filter to')
    ap.add_argument('files', metavar='FILE', nargs='+',
                    help='Input PubTator files')
    return ap

def read_id_list(fn):
    with open(fn) as f:
        return [l.rstrip('\n') for l in f.readlines()]

def filter_pubtator(fn, ids, out=sys.stdout):
    with open(fn) as f:
        in_valid = False
        for i, line in enumerate(f, start=1):
            m = ID_RE.match(line)
            if m and m.group(1) in ids:
                out.write(line)
                in_valid = True
            else:
                if in_valid:
                    out.write('\n') # empty lines separate documents
                in_valid = False
            if i%100000 == 0:
                print('Processed {} lines ...'.format(i), file=sys.stderr)
        print('Done, processed {} lines.'.format(i), file=sys.stderr)

def main(argv):
    args = argparser().parse_args(argv[1:])
    ids = set(read_id_list(args.idlist))
    for fn in args.files:
        filter_pubtator(fn, ids)

if __name__ == '__main__':
    sys.exit(main(sys.argv))

