#!/usr/bin/env python

# Get string to ID mappings from Web Annotation data.

from __future__ import print_function

import sys
import os
import json

from logging import info, warn, error
import logging

from webannotation import read_annotations, SpanAnnotation


logging.basicConfig(level=logging.INFO)


def pretty_dumps(obj):
    return json.dumps(obj, sort_keys=True, indent=2, separators=(',', ': '))


def argparser():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('-r', '--recurse', default=False, action='store_true',
                    help='Recurse into subdirectories')
    ap.add_argument('files', metavar='FILE', nargs='+',
                    help='Input annotation files')
    return ap


def process_file(fn, mappings):
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
        text, id_ = a.text, a.body['id']
        if text not in mappings:
            mappings[text] = {}
        if id_ not in mappings[text]:
            mappings[text][id_] = 0
        mappings[text][id_] += 1


def process(files, args, mappings=None, count=0, recursed=False):
    if mappings is None:
        mappings = {}

    for fn in files:
        _, ext = os.path.splitext(fn)
        if recursed and ext == '.txt':
            pass
        elif os.path.isfile(fn):
            process_file(fn, mappings)
            count += 1
        elif os.path.isdir(fn):
            if args.recurse:
                df = [os.path.join(fn, n) for n in os.listdir(fn)]
                mappings, count = process(df, args, mappings, count, True)
            else:
                info('skipping directory {}'.format(fn))
        else:
            info('skipping {}'.format(fn))
        if count % 100 == 0:
            info('Processed {} documents ...'.format(count))

    return mappings, count


def main(argv):
    args = argparser().parse_args(argv[1:])
    mappings, count = process(args.files, args)
    info('Done, processed {} documents.'.format(count))
    print(pretty_dumps(mappings))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
