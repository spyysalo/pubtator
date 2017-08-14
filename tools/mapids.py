#!/usr/bin/env python

# Modify "id" values in JSON data according to wrapping.

from __future__ import print_function

import sys
import json
import logging

from collections import defaultdict
from logging import info, warn, error


class FormatError(Exception):
    pass


def pretty_dump(obj, out=sys.stdout):
    return json.dump(obj, out, sort_keys=True, indent=2, separators=(',', ': '))


def argparser():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('-p', '--prefix', default='NCBIGENE',
                    help='Namespace prefix of IDs to map')
    ap.add_argument('-v', '--verbose', default=False, action='store_true',
                    help='Verbose output')
    ap.add_argument('idmap', metavar='IDFILE',
                    help='File with ID mapping')
    ap.add_argument('files', metavar='FILE', nargs='+',
                    help='Files or directories to merge')
    return ap


def read_mapping(fn):
    read = 0
    mapping = defaultdict(list)
    with open(fn) as f:
        for i, l in enumerate(f, start=1):
            l = l.rstrip('\n')
            f = l.split('\t')
            if len(f) != 3:
                raise FormatError('expected 3 TAB-separated values, got {} on line {} in {}: {}'.format(len(f), i, fn, l))
            id1, id_type, id2 = f
            mapping[id1].append((id_type, id2))
            read += 1
    info('Read {} from {}'.format(read, fn))
    return mapping


def map_id(id_, mapping, options=None):
    if options and options.prefix:
        if not id_.startswith(options.prefix):
            return id_    # prefix filter
    if id_ not in mapping:
        map_id.stats['missing'] += 1
        return id_
    else:
        mapped = [mid for id_type, mid in mapping[id_]]
        if len(mapped) == 1:
            mapped = mapped[0]
        else:
            map_id.stats['multiple'] += 1
            warn('{} maps to multiple, arbitrarily using first: {}'.format(id_, ', '.join(mapped)))
            mapped = mapped[0]    # TODO better resolution
        map_id.stats['mapped'] += 1
        return mapped
map_id.stats = defaultdict(int)


def map_id_stats():
    return ', '.join('{} {}'.format(s, v)
                     for s, v in sorted(map_id.stats.items()))


def map_ids(data, mapping, options=None):
    if isinstance(data, list):
        for d in data:
            map_ids(d, mapping, options)
    elif isinstance(data, dict):
        if 'id' in data:
            data['id'] = map_id(data['id'], mapping, options)
        for k, v in data.iteritems():
            if isinstance(v, (list, dict)):
                map_ids(v, mapping, options)
    return data


def map_file_ids(fn, mapping, options=None):
    with open(fn) as f:
        data = json.load(f)
    map_ids(data, mapping, options)
    with open(fn, 'wt') as f:
        pretty_dump(data, f)


def main(argv):
    args = argparser().parse_args(argv[1:])
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    mapping = read_mapping(args.idmap)

    errors = 0
    for i, fn in enumerate(args.files, start=1):
        try:
            map_file_ids(fn, mapping, args)
        except Exception, e:
            logging.error('failed {}: {}'.format(fn, e))
            errors += 1
        if i % 100 == 0:
            info('Processed {} documents ...'.format(i))

    info('Done, processed {} documents ({} errors).'.format(i, errors))
    info(map_id_stats())
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
