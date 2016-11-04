#!/usr/bin/env python

# Convert PubTator format to other formats.

import sys
import re
import codecs
import collections
import itertools
import json

from os import path, makedirs
from errno import EEXIST
from logging import warn

DEFAULT_ENCODING = 'utf-8'

FORMATS = ['standoff', 'json', 'oa-jsonld', 'wa-jsonld']
DEFAULT_FORMAT = 'standoff'

# Regular expressions matching PubTator format embedded text, span
# annotation, and relation annotation.
TEXT_RE = re.compile(r'^(\d+)\|(.)\|(.*)$')
SPAN_RE = re.compile(r'^(\d+)\t(\d+)\t(\d+)\t([^\t]+)\t(\S+)\t(\S*)(?:\t(.*))?\s*$')
REL_RE = re.compile(r'^(\d+)\t(\S+)\t(\S+)\t(\S+)\s*$')

def argparser():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('-e', '--encoding', default=DEFAULT_ENCODING,
                    help='Encoding (default %s)' % DEFAULT_ENCODING)
    ap.add_argument('-f', '--format', default=DEFAULT_FORMAT, choices=FORMATS,
                    help='Output format (default %s)' % DEFAULT_FORMAT)
    ap.add_argument('-i', '--ids', metavar='FILE', default=None,
                    help='Restrict to documents with IDs in file')
    ap.add_argument('-o', '--output', metavar='DIR', default=None,
                    help='Output directory')
    ap.add_argument('-s', '--subdirs', default=True, action='store_true',
                    help='Create subdirectories by document ID prefix.')
    ap.add_argument('files', metavar='FILE', nargs='+',
                    help='Input PubTator files')
    return ap

class ParseError(Exception):
    pass

def pretty_dumps(obj):
    return json.dumps(obj, sort_keys=True, indent=2, separators=(',', ': '))

def encoding(options):
    try:
        return options.encoding
    except:
        return DEFAULT_ENCODING

def next_id(prefix, ann_by_id):
    for i in itertools.count(1):
        if prefix+str(i) not in ann_by_id:
            return prefix+str(i)

def guess_namespace(type_):
    if type_ == 'Species':
        return 'taxonomy'
    elif type_ == 'Gene':
        return 'EGID'    # Entrez gene ID
    elif type_ == 'Chemical':
        return 'MESH'
    else:
        return 'unknown'

class SpanAnnotation(object):
    def __init__(self, docid, start, end, text, type_, norm, substrings):
        self.docid = docid
        self.start = int(start)
        self.end = int(end)
        self.text = text
        self.type = type_
        self._norm = norm
        # substrings capture cases such as
        #     2234245	314	341	visual or auditory toxicity	Disease	D014786|D006311	visual toxicity|auditory toxicity
        self.substrings = substrings

    @property
    def norm(self):
        if not self._norm.strip():
            return None
        elif ':' in self._norm:
            return self._norm
        else:
            # Norm value, but no namespace; add a guess
            return guess_namespace(self.type) + ':' + self._norm

    def to_dict(self):
        d = {
            'start': self.start,
            'end': self.end,
            'text': self.text,
            'type': self.type,
        }
        if self.norm:
            d['norm'] = self.norm
        return d

    def to_jsonld_dict(self, docurl, idx, oa=True):
        if oa:
            id_key, type_key = '@id', '@type'
            id_val = docurl + '/annotations/%d' % idx
        else:
            id_key, type_key = 'id', 'type'
            id_val = docurl + '/ann/%d' % idx
        d = {
            id_key : id_val,
            type_key : self.type,
            'target' : docurl + '/text#char=%d,%d' % (self.start, self.end),
            'text': self.text,
        }
        if self.norm:
            d['body'] = self.norm
        return d

    def to_oa_jsonld_dict(self, docurl, idx):
        return self.to_jsonld_dict(docurl, idx, oa=True)

    def to_wa_jsonld_dict(self, docurl, idx):
        return self.to_jsonld_dict(docurl, idx, oa=False)

    def to_json(self):
        return pretty_dumps(self.to_dict())

    def to_oa_jsonld(self, docurl, idx):
        return pretty_dumps(self.to_oa_jsonld_dict(docurl, idx))

    def to_wa_jsonld(self, docurl, idx):
        return pretty_dumps(self.to_wa_jsonld_dict(docurl, idx))

    def to_ann_lines(self, ann_by_id=None):
        # TODO: substrings
        if ann_by_id is None:
            ann_by_id = {}
        tid = next_id('T', ann_by_id)
        t_ann = '%s\t%s %s %s\t%s' % (
            tid, self.type, self.start, self.end, self.text)
        ann_by_id[tid] = t_ann
        if not self.norm:
            return [t_ann]    # No norm
        else:
            nid = next_id('N', ann_by_id)
            n_ann = '%s\tReference %s %s\t%s' % (nid, tid, self.norm, self.text)
            ann_by_id[nid] = n_ann
            return [t_ann, n_ann]
        
    @classmethod
    def from_string(cls, s):
        m = SPAN_RE.match(s)
        if not m:
            raise ParseError('Failed to parse as span: "%s"' % s)
        return cls(*m.groups())
        
class RelationAnnotation(object):
    def __init__(self, docid, type_, arg1, arg2):
        self.docid = docid
        self.type = type_
        self.arg1 = arg1
        self.arg2 = arg2

    def to_dict(self):
        raise NotImplementedError()    # TODO

    def to_json(self):
        return pretty_dumps(self.to_dict())

    def to_ann_lines(self, idseq=0):
        # No direct support for document-level relation annotations in
        # .ann output format; skip for now.
        raise NotImplementedError
        
    @classmethod
    def from_string(cls, s):
        m = REL_RE.match(s)
        if not m:
            raise ParseError(s)
        return cls(*m.groups())

class PubTatorDocument(object):
    def __init__(self, id_, text_sections, annotations):
        self.id = id_
        self.text_sections = text_sections
        self.annotations = annotations

    @property
    def text(self):
        return '\n'.join(text for label, text in self.text_sections)

    @property
    def title(self):
        return ' '.join(text for label, text in self.text_sections
                        if label == 't')

    def text_dict(self):
        return {
            '_id': self.id,
            'title': self.title,
            'abstract': [ {
                'text': text
            } for label, text in self.text_sections if label == 'a' ]
        }

    def ann_dict(self):
        return {
            'annotations': [ a.to_dict() for a in self.annotations ]
        }

    def text_json(self):
        return pretty_dumps(self.text_dict())

    def ann_json(self):
        return pretty_dumps(self.ann_dict())

    def ann_oa_jsonld(self):
        u = 'pubmed/' + self.id
        return pretty_dumps([
            a.to_oa_jsonld_dict(u, i) for i, a in enumerate(self.annotations)
        ])

    def ann_wa_jsonld(self):
        u = 'PMID:' + self.id
        return pretty_dumps([
            a.to_wa_jsonld_dict(u, i) for i, a in enumerate(self.annotations)
        ])

    def to_json(self):
        d = self.text_dict()
        d.update(self.ann_dict())
        return pretty_dumps(d)

    def to_oa_jsonld(self):
        return self.ann_oa_jsonld()    # TODO: text?

    def to_wa_jsonld(self):
        return self.ann_wa_jsonld()

class LookaheadIterator(collections.Iterator):
    """Lookahead iterator from http://stackoverflow.com/a/1518097."""
    def __init__(self, it):
        self._it, self._nextit = itertools.tee(iter(it))
        self.index = -1
        self._advance()
        
    def _advance(self):
        self.lookahead = next(self._nextit, None)
        self.index = self.index + 1
        
    def next(self):
        self._advance()
        return next(self._it)
        
    def __nonzero__(self):
        return self.lookahead is not None

def is_text_line(line):
    return TEXT_RE.match(line.rstrip('\n\r'))

def is_span_line(line):
    return SPAN_RE.match(line.rstrip('\n\r'))

def is_rel_line(line):
    return REL_RE.match(line.rstrip('\n\r'))

def read_pubtator_document(fl):
    """Read from LookaheadIterator, return PubTatorDocument."""
    assert isinstance(fl, LookaheadIterator)
    document_id = None
    text_sections = []
    while not fl.lookahead.strip():
        next(fl)    # skip initial empty lines
    for line in fl:
        m = TEXT_RE.match(line.rstrip('\n\r'))
        if not m:
            raise ParseError('%d: %s' % (fl.index, line))
        docid, type_, text = m.groups()
        if document_id is not None and docid != document_id:
            raise ParseError('%d: %s' % (fl.index, line))
        document_id = docid
        if text.strip():
            text_sections.append((type_, text))
        if not is_text_line(fl.lookahead):
            break

    annotations = []
    for line in fl:
        if not line.strip():
            break
        if is_span_line(line):
            annotations.append(SpanAnnotation.from_string(line))
        elif is_rel_line(line):
            annotations.append(RelationAnnotation.from_string(line))
        else:
            raise ParseError('line %d: %s' % (fl.index, line))

    return PubTatorDocument(document_id, text_sections, annotations)

def skip_pubtator_document(fl, ids):
    """Skip the next document from LookaheadIterator if its ID is not in
    the given list, return whether skipped."""
    if not ids:
        return False
    while not fl.lookahead.strip():
        next(fl)    # skip initial empty lines
    line = fl.lookahead
    m = TEXT_RE.match(line.rstrip('\n\r'))
    if not m:
        raise ParseError('%d: %s' % (fl.index, line))
    docid, _, _ = m.groups()
    if docid in ids:
        return False
    for line in fl:
        if not line.strip():
            break
    return True

def recover_from_error(fl):
    """Skip remaining lines of current document."""
    assert isinstance(fl, LookaheadIterator)
    for line in fl:
        if not line.strip():
            break

def read_pubtator(fl, ids):
    """Read PubTator format from file-like object, yield PubTatorDocuments."""

    lines = LookaheadIterator(fl)
    while lines:
        if skip_pubtator_document(lines, ids):
            continue
        try:
            yield read_pubtator_document(lines)
        except ParseError, e:
            warn('Error reading {}: {} (skipping...)'.format(fl.name, e))
            recover_from_error(lines)

def safe_makedirs(path):
    """Create directory path if it doesn't already exist."""
    # From http://stackoverflow.com/a/5032238
    try:
        makedirs(path)
    except OSError, e:
        if e.errno != EEXIST:
            raise

def output_filename(document, suffix, options):
    try:
        outdir = options.output if options.output is not None else ''
    except:
        outdir = ''
    if options is not None and options.subdirs:
        outdir = path.join(outdir, document.id[:4])
    safe_makedirs(outdir)
    return path.join(outdir, document.id + suffix)

def write_text(document, options=None):
    textout = output_filename(document, '.txt', options)
    with codecs.open(textout, 'wt', encoding=encoding(options)) as txt:
        txt.write(document.text)
        if not document.text.endswith('\n'):
            txt.write('\n')

def write_standoff(document, options=None):
    write_text(document, options)
    annout = output_filename(document, '.ann', options)
    ann_by_id = {}
    with codecs.open(annout, 'wt', encoding=encoding(options)) as ann:
        for pa_ann in document.annotations:
            if not isinstance(pa_ann, SpanAnnotation):
                warn('not converting %s' % type(pa_ann).__name__)    # TODO
                continue
            for so_ann in pa_ann.to_ann_lines(ann_by_id):
                print >> ann, so_ann

def write_json(document, options=None):
    write_text(document, options)
    outfn = output_filename(document, '.json', options)
    with codecs.open(outfn, 'wt', encoding=encoding(options)) as out:
        out.write(document.to_json())

def write_oa_jsonld(document, options=None):
    write_text(document, options)
    outfn = output_filename(document, '.jsonld', options)
    with codecs.open(outfn, 'wt', encoding=encoding(options)) as out:
        out.write(document.to_oa_jsonld())

def write_wa_jsonld(document, options=None):
    write_text(document, options)
    outfn = output_filename(document, '.jsonld', options)
    with codecs.open(outfn, 'wt', encoding=encoding(options)) as out:
        out.write(document.to_wa_jsonld())

def convert(fn, writer, options=None):
    with codecs.open(fn, 'rU', encoding=encoding(options)) as fl:
        for i, document in enumerate(read_pubtator(fl, options.ids), start=1):
            if i % 100 == 0:
                print >> sys.stderr, 'Processed %d documents ...' % i
            writer(document, options)
    print >> sys.stderr, 'Done, processed %d documents.' % i

def read_id_list(fn):
    with open(fn) as f:
        return [l.rstrip('\n') for l in f.readlines()]

def main(argv):
    args = argparser().parse_args(argv[1:])

    if args.ids:
        args.ids = set(read_id_list(args.ids))

    if args.format == 'standoff':
        writer = write_standoff
    elif args.format == 'json':
        writer = write_json
    elif args.format == 'oa-jsonld':
        writer = write_oa_jsonld
    elif args.format == 'wa-jsonld':
        writer = write_wa_jsonld
    else:
        raise ValueError('unknown format %s' % args.format)

    for fn in args.files:
        convert(fn, writer, args)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
