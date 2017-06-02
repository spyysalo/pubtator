#!/usr/bin/env python

# Write related entities

from __future__ import print_function

import sys
import os
import json
import logging

from logging import info, warn, error

from webannotation import read_annotations, SpanAnnotation, RelationAnnotation


logging.basicConfig(level=logging.INFO)


def argparser():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('-r', '--recurse', default=False, action='store_true',
                    help='Recurse into subdirectories')
    ap.add_argument('files', metavar='FILE', nargs='+',
                    help='Input annotation files')
    return ap


def identity(ann):
    """Return a string identifying the annotated entity."""
    ent = ann.body.get('id')
    if ent is not None:
        return ent
    else:
        # For unnormalized entities (no body.id) use the lowercase
        # annotated text as an approximation.
        return 'text:{}'.format(ann.text.lower())


def pair_identity(ann1, ann2):
    """Return hashable identifying an unordered pair of annotated entities."""
    i1, i2 = identity(ann1), identity(ann2)
    if i1 < i2:
        i1, i2 = i2, i1    # arbitrary but fixed
    return (i1, i2)


def process_file(fn):
    try:
        annotations = read_annotations(fn)
    except Exception, e:
        error('failed to parse {}: {}'.format(fn, e))
        raise
    spans = [a for a in annotations if isinstance(a, SpanAnnotation)]
    rels = [a for a in annotations if isinstance(a, RelationAnnotation)]
    span_by_id = { s.id: s for s in spans }

    for r in rels:
        from_ = span_by_id[r.body['from']]
        to = span_by_id[r.body['to']]
        print(pair_identity(from_, to))


def process(files, args, count=0, recursed=False):
    for fn in files:
        _, ext = os.path.splitext(fn)
        if recursed and ext == '.txt':
            pass
        elif os.path.isfile(fn):
            process_file(fn)
            count += 1
        elif os.path.isdir(fn):
            if args.recurse:
                df = [os.path.join(fn, n) for n in os.listdir(fn)]
                count = process(df, args, count, True)
            else:
                info('skipping directory {}'.format(fn))
        else:
            info('skipping {}'.format(fn))
        if count % 100 == 0:
            info('Processed {} documents ...'.format(count))

    return count


def main(argv):
    args = argparser().parse_args(argv[1:])
    count = process(args.files, args)
    info('Done, processed {} documents.'.format(count))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
