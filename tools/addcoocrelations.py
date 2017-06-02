#!/usr/bin/env python

# Add cooccurrence relations to converted PubTator data

from __future__ import print_function

import sys
import json
import logging

from collections import defaultdict
from logging import debug, info, warn, error

from webannotation import read_annotations, SpanAnnotation, RelationAnnotation


logging.basicConfig(level=logging.INFO)


def argparser():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('-d', '--distance', metavar='CHARS', type=int, default=None,
                    help='Character distance-based cooc (default sentence)')
    ap.add_argument('-r', '--include-repeated', default=False,
                    action='store_true',
                    help='Include repeated entity cooccurrences in context')
    ap.add_argument('-s', '--include-self', default=False, action='store_true',
                    help='Include cooccurrences of entities with themselves')
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


class Cooccurrence(RelationAnnotation):
    def __init__(self, id_, ann1, ann2):
        if ann1.document != ann2.document:
            raise ValueError('cooccurrence across documents')
        doc = ann1.document
        # Cooccurrence is symmetric. For consistency and ease of
        # access, order "from_" and "to" so that the "body" reference
        # in the former is alphabetically before that of the latter
        # (arbitrary but fixed order).
        if ann1.body.get('id', '') > ann2.body.get('id', ''):
            ann1, ann2 = ann2, ann1
        super(Cooccurrence, self).__init__(id_, 'Relation', doc, ann1.id,
                                           ann2.id, 'Cooccurrence')


def span_distance(a, b):
    if a.start < b.start:
        first, second = a, b
    else:
        first, second = b, a
    if first.end > second.start:
        return 0    # overlap
    else:
        return second.start - first.end


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


def cooccurrences(annotations, options=None):
    """Return cooccurrences with optional distance filtering."""

    relations = []
    seen = set()

    max_distance = options.distance if options else None
    include_identical = options.include_self if options else False
    include_repeated = options.include_repeated if options else False

    # filter annotations to relevant ones
    filtered = [
        a for a in annotations
        if (isinstance(a, SpanAnnotation) and
            a.body.get('type', '').lower() not in ('sentence', 'title'))
    ]
    if filtered != annotations:
        debug('filtered {} annotations to {}'.format(
            len(annotations), len(filtered)))
        annotations = filtered

    next_id = max_id_base(annotations) + 1
    for i in range(len(annotations)):
        for j in range(i+1, len(annotations)):
            a, b = annotations[i], annotations[j]
            if a.document != b.document:
                warn('annotations for different documents')
                continue
            if max_distance is not None and span_distance(a, b) > max_distance:
                continue
            if identity(a) == identity(b) and not include_identical:
                continue
            pid = pair_identity(a, b)
            if pid in seen and not include_repeated:
                continue
            seen.add(pid)
            id_ = '{}/{}'.format(a.id_path(), next_id)
            next_id += 1
            r = Cooccurrence(id_, a, b)
            relations.append(r)
    return relations


def sentence_cooccurrences(annotations, options=None):
    """Return sentence-level cooccurrences."""

    sentences = [
        a for a in annotations
        if (isinstance(a, SpanAnnotation) and
            a.body.get('type', '').lower() == 'sentence')
    ]
    anns = [
        a for a in annotations
        if (isinstance(a, SpanAnnotation) and
            a.body.get('type', '').lower() not in ('sentence', 'title'))
    ]
    if anns and not sentences:
        raise ValueError('no sentences for annotations')

    # create mapping from offset to sentence
    sent_by_offset = {}
    for s in sentences:
        for i in range(s.start, s.end):
            if i in sent_by_offset:
                warn('overlapping sentences')
            sent_by_offset[i] = s

    # group annotations by sentence
    ann_by_sent = defaultdict(list)
    for a in anns:
        s = None
        for i in range(a.start, a.end):
            s = sent_by_offset.get(i)
            if s is not None:
                # TODO consider checking for annotations spanning
                # multiple sentences
                break
        if s is not None:
            ann_by_sent[s].append(a)
        else:
            warn('failed to find sentence for annotation')

    # create co-occurrences within each sentence
    relations = []
    for s, a in ann_by_sent.items():
        relations.extend(cooccurrences(a))
    return relations


def process(fn, options=None):
    try:
        annotations = read_annotations(fn)
    except Exception, e:
        error('failed to parse {}: {}'.format(fn, e))
        raise
    if options and options.distance:
        # Distance-based cooccurrences
        relations = cooccurrences(annotations, options)
    else:
        # Sentence-level cooccurrences
        relations = sentence_cooccurrences(annotations, options)
    annotations.extend(relations)
    with open(fn, 'wt') as f:
        f.write(pretty_dumps([a.to_dict() for a in annotations]))


def main(argv):
    args = argparser().parse_args(argv[1:])

    errors = 0
    for i, fn in enumerate(args.files, start=1):
        try:
            process(fn, args)
        except Exception, e:
            logging.error('failed {}: {}'.format(fn, e))
            errors += 1
        if i % 100 == 0:
            info('Processed {} documents ...'.format(i))
    info('Done, processed {} documents ({} errors).'.format(i, errors))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
