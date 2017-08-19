# Support for Web Annotation format.

import re
import json

from urlparse import urldefrag
from logging import warn, error


def pretty_dumps(obj):
    return json.dumps(obj, sort_keys=True, indent=2, separators=(',', ': '))


class FormatError(Exception):
    pass


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

    def remap_ids(self, id_map):
        self.id = id_map.get(self.id, self.id)

    @staticmethod
    def from_dict(d):
        if 'type' not in d:
            raise NotImplementedError('annotation without type: {}'.format(d))
        if d['type'] == 'Span':
            return SpanAnnotation.from_dict(d)
        elif d['type'] == 'Relation':
            return RelationAnnotation.from_dict(d)
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

    def remap_ids(self, id_map):
        super(RelationAnnotation, self).remap_ids(id_map)
        self.body['from'] = id_map.get(self.body['from'], self.body['from'])
        self.body['to'] = id_map.get(self.body['to'], self.body['to'])

    @classmethod
    def from_dict(cls, d):
        id_ = d.pop('id')
        type_ = d.pop('type')
        target = d.pop('target')
        body = d.pop('body')
        if d:
            warn('RelationAnnotation.from_text: extra data: {}'.format(d))
        from_ = body.pop('from')
        to = body.pop('to')
        rel_type = body.pop('type')
        if d:
            warn('RelationAnnotation.from_text: extra data in body: {}'.format(
                body))
        return cls(id_, type_, target, from_, to, rel_type)


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

    def __str__(self):
        return '{} {} {} ("{}") {}'.format(self.id, self.type, self.target, self.text, self.body)

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
    annotations, ids = [], set()
    for d in data:
        a = Annotation.from_dict(d)
        if a.id in ids:
            raise FormatError('duplicate id in {}: {}'.format(fn, a.id))
        else:
            ids.add(a.id)
        annotations.append(a)
    return annotations


def read_annotations(fn):
    if fn.endswith('.jsonld'):
        return read_jsonld_annotations(fn)
    else:
        raise NotImplementedError('non-JSON-LD not supported: {}'.format(fn))
