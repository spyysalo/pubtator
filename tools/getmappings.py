#!/usr/bin/env python

# Get string to ID mappings from Web Annotation data.

from __future__ import print_function

import sys
import os
import json
import logging

from collections import defaultdict
from logging import info, warn, error

from webannotation import read_annotations, SpanAnnotation


logging.basicConfig(level=logging.INFO)


def pretty_dumps(obj):
    return json.dumps(obj, sort_keys=True, indent=2, separators=(',', ': '))


def argparser():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('-a', '--all', default=False, action='store_true',
                    help='Output all mappings')
    ap.add_argument('-c', '--min-count', default=0, type=int,
                    help='Minimum occurrence count for included mappings')
    ap.add_argument('-r', '--recurse', default=False, action='store_true',
                    help='Recurse into subdirectories')
    ap.add_argument('-R', '--min-ratio', default=0, type=float,
                    help='Minimum ratio to most frequent for included mappings')
    ap.add_argument('files', metavar='FILE', nargs='+',
                    help='Input annotation files')
    return ap


def exclude_mapping(text, id_, type_, options):
    if options.all:
        return False
    # filter cancer hallmarks (sentence-level annotation)
    if 'hallmark' in type_.lower():
        return True


def process_file(fn, options, mappings):
    try:
        annotations = read_annotations(fn)
    except Exception, e:
        error('failed to parse {}: {}'.format(fn, e))
        raise
    for a in annotations:
        if not isinstance(a, SpanAnnotation):
            continue
        if 'id' not in a.body:
            continue
        text, id_, type_ = a.text, a.body['id'], a.body.get('type')
        if exclude_mapping(text, id_, type_, options):
            continue
        if text not in mappings:
            mappings[text] = {}
        if id_ not in mappings[text]:
            mappings[text][id_] = 0
        mappings[text][id_] += 1


def process(files, options, mappings=None, count=0, recursed=False):
    if mappings is None:
        mappings = {}

    for fn in files:
        _, ext = os.path.splitext(fn)
        if recursed and ext == '.txt':
            pass
        elif os.path.isfile(fn):
            process_file(fn, options, mappings)
            count += 1
        elif os.path.isdir(fn):
            if options.recurse:
                df = [os.path.join(fn, n) for n in os.listdir(fn)]
                mappings, count = process(df, options, mappings, count, True)
            else:
                info('skipping directory {}'.format(fn))
        else:
            info('skipping {}'.format(fn))
        if count % 100 == 0:
            info('Processed {} documents ...'.format(count))

    return mappings, count


def filter_mappings(mappings, options):
    filtered = 0

    if options.min_count > 0:
        for mention, mapping in mappings.iteritems():
            for id_ in mapping.keys():
                if mapping[id_] < options.min_count:
                    del mapping[id_]
                    filtered += 1

    if options.min_ratio > 0:
        for mention, mapping in mappings.iteritems():
            max_count = max(mapping.values())
            for id_ in mapping.keys():
                if 1.*mapping[id_] / max_count < options.min_ratio:
                    del mapping[id_]
                    filtered += 1

    kept = 0
    for mention in mappings.keys():
        if len(mappings[mention]) == 0:
            del mappings[mention]
        else:
            kept += len(mappings[mention])

    info('Filtered {}, kept {}'.format(filtered, kept))
    return mappings


def write_statistics(mappings, write=info):
    mentions = 0
    strings, amb_strings = len(mappings), 0
    id_count = defaultdict(int)
    for mention, mapping in mappings.iteritems():
        mentions += sum(mapping.values())
        if len(mapping) > 1:
            amb_strings += 1
        for id_ in mapping:
            id_count[id_] += 1
    ids, amb_ids = len(id_count), len([i for i, c in id_count.items() if c > 1])

    write('{} strings, {} ({:.1%}) ambiguous'.format(
        strings, amb_strings, 1.*amb_strings/strings))
    write('{} ids, {} ({:.1%}) ambiguous'.format(
        ids, amb_ids, 1.*amb_ids/ids))
    write('{} total mentions'.format(mentions))


def main(argv):
    args = argparser().parse_args(argv[1:])
    mappings, count = process(args.files, args)
    info('Done, processed {} documents.'.format(count))
    mappings = filter_mappings(mappings, args)
    write_statistics(mappings)
    print(pretty_dumps(mappings))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
