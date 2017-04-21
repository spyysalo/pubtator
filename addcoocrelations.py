#!/usr/bin/env python

# Add cooccurrence relations to converted PubTator data

from __future__ import print_function

import sys
import json

from logging import info, warn, error
import logging

from webannotation import read_annotations, RelationAnnotation


logging.basicConfig(level=logging.INFO)


def argparser():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('files', metavar='FILE', nargs='+',
                    help='Input annotation files')
    return ap


def pretty_dumps(obj):
    return json.dumps(obj, sort_keys=True, indent=2, separators=(',', ': '))


def max_id_base(annotations):
    max_ = 0
    for a in annotations:
        try:
            i = int(a.id_base())
        except:
            warn('non-int ID base: {}'.format(a.id_base()))
            continue
        max_ = max(i, max_)
    return max_


def cooccurrences(annotations):
    relations = []
    next_id = max_id_base(annotations) + 1
    for i in range(len(annotations)):
        for j in range(i+1, len(annotations)):
            a, b = annotations[i], annotations[j]
            if a.document != b.document:
                warn('annotations for different documents')
                continue
            if a.start < b.start:
                first, second = a, b
            else:
                first, second = b, a
            distance = second.start - first.end
            if distance > 100:    # TODO do sentence coocc instead
                continue
            id_ = '{}/{}'.format(a.id_path(), next_id)
            next_id += 1
            r = RelationAnnotation(id_, 'Relation', a.document, a.id, b.id,
                                   'Cooccurrence')
            relations.append(r)
    return relations


def process(fn):
    try:
        annotations = read_annotations(fn)
    except Exception, e:
        error('failed to parse {}: {}'.format(fn, e))
        raise
    relations = cooccurrences(annotations)
    annotations.extend(relations)
    with open(fn, 'wt') as f:
        f.write(pretty_dumps([a.to_dict() for a in annotations]))


def main(argv):
    args = argparser().parse_args(argv[1:])

    for i, fn in enumerate(args.files, start=1):
        process(fn)
        if i % 100 == 0:
            info('Processed {} documents ...'.format(i))
    info('Done, processed {} documents.'.format(i))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
