#!/usr/bin/env python

# Add cooccurrence relations to converted PubTator data

from __future__ import print_function

import sys
import json
import re
import six

from urlparse import urldefrag
from logging import info, warn, error
import logging

logging.basicConfig(level=logging.INFO)


def argparser():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('files', metavar='FILE', nargs='+',
                    help='Input annotation files')
    return ap


def pretty_dumps(obj):
    return json.dumps(obj, sort_keys=True, indent=2, separators=(',', ': '))


class Annotation(object):
    """Web Annotation."""

    def __init__(self, id_, type_, target, body):
        self.id = id_
        self.type = type_
        self.target = target
        self.body = body

    @property
    def document(self):
        # return urldefrag(self.target)[0]    # lowercases namespace
        return self.target.split('#')[0]

    def id_base(self):
        return self.id.split('/')[-1]

    def id_path(self):
        return '/'.join(self.id.split('/')[:-1])

    def to_dict(self):
        raise NotImplementedError()
        
    @staticmethod
    def from_dict(d):
        if 'type' not in d:
            raise NotImplementedError('annotation without type: {}'.format(d))
        if d['type'] == 'Span':
            return SpanAnnotation.from_dict(d)
        else:
            raise NotImplementedError('annotation type {}'.format(d['type']))


class RelationAnnotation(Annotation):
    def __init__(self, id_, type_, target, from_, to, rel_type):
        body = {
            'from': from_,
            'to': to,
            'type': rel_type
        }
        super(RelationAnnotation, self).__init__(id_, type_, target, body)

    def to_dict(self):
        d = {
            'id': self.id,
            'type': self.type,
            'target': self.target,
            'body': self.body,
        }
        return d

    def to_json(self):
        return pretty_dumps(self.to_dict())


class SpanAnnotation(Annotation):
    def __init__(self, id_, type_, target, body, text, other=None):
        super(SpanAnnotation, self).__init__(id_, type_, target, body)
        self.text = text
        self.other = other

    @property
    def char_range(self):
        fragment = urldefrag(self.target)[1]
        m = re.match('^char=(\d+),(\d+)$', fragment)
        if not m:
            raise ValueError('failed to parse fragment: {}'.format(fragment))
        return int(m.group(1)), int(m.group(2))
        
    @property
    def start(self):
        return self.char_range[0]

    @property
    def end(self):
        return self.char_range[1]
    
    def to_dict(self):
        d = {
            'id': self.id,
            'type': self.type,
            'target': self.target,
            'body': self.body,
            'text': self.text,
        }
        if self.other:
            d.update(self.other)
        return d

    def to_json(self):
        return pretty_dumps(self.to_dict())

    @classmethod
    def from_dict(cls, d):
        id_ = d.pop('id')
        type_ = d.pop('type')
        target = d.pop('target')
        body = d.pop('body')
        text = d.pop('text')
        if d:
            warn('SpanAnnotation.from_text: extra data: {}'.format(d))
        return cls(id_, type_, target, body, text, d)


def read_jsonld_annotations(fn):
    with open(fn) as f:
        data = json.loads(f.read())
    annotations = []
    for d in data:
        annotations.append(Annotation.from_dict(d))
    return annotations


def read_annotations(fn):
    if fn.endswith('.jsonld'):
        return read_jsonld_annotations(fn)
    else:
        raise NotImplementedError('non-JSON-LD not supported: {}'.format(fn))


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

    errors = 0
    for i, fn in enumerate(args.files, start=1):
        try:
            process(fn)
        except Exception, e:
            logging.error('failed {}: {}'.format(fn, e))
            errors += 1
        if i % 100 == 0:
            info('Processed {} documents ...'.format(i))
    info('Done, processed {} documents ({} errors).'.format(i, errors))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
