#!/usr/bin/env python

# Get string to ID mappings from Web Annotation data.

from __future__ import print_function

import sys
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
    ap.add_argument('files', metavar='FILE', nargs='+',
                    help='Input annotation files')
    return ap


def process(fn, mappings):
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


def main(argv):
    args = argparser().parse_args(argv[1:])

    mappings = {}
    for i, fn in enumerate(args.files, start=1):
        process(fn, mappings)
        if i % 100 == 0:
            info('Processed {} documents ...'.format(i))
    info('Done, processed {} documents.'.format(i))
    print(pretty_dumps(mappings))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
