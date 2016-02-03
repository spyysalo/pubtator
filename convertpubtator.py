#!/usr/bin/env python

# Convert PubTator format to brat-flavored standoff.

import sys
import re
import codecs
import collections
import itertools

from os import path
from logging import warn

DEFAULT_ENCODING = 'utf-8'

# Regular expressions matching PubTator format embedded text, span
# annotation, and relation annotation.
TEXT_RE = re.compile(r'^(\d+)\|(.)\|(.*)$')
SPAN_RE = re.compile(r'^(\d+)\t(\d+)\t(\d+)\t([^\t]+)\t(\S+)\t(\S*)(?:\t(.*))?\s*$')
REL_RE = re.compile(r'^(\d+)\t(\S+)\t(\S+)\t(\S+)\s*$')

def argparser():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', '--output', metavar='DIR', default=None,
                    help='Output directory')
    ap.add_argument('-e', '--encoding', default=DEFAULT_ENCODING,
                    help='Encoding (default %s)' % DEFAULT_ENCODING)
    ap.add_argument('files', metavar='FILE', nargs='+',
                    help='Input PubTator files')
    return ap

class ParseError(Exception):
    pass

def next_id(prefix, ann_by_id):
    for i in itertools.count(1):
        if prefix+str(i) not in ann_by_id:
            return prefix+str(i)

class SpanAnnotation(object):
    def __init__(self, docid, start, end, text, type_, norm, substrings):
        self.docid = docid
        self.start = start
        self.end = end
        self.text = text
        self.type = type_
        self.norm = norm
        # substrings capture cases such as
        #     2234245	314	341	visual or auditory toxicity	Disease	D014786|D006311	visual toxicity|auditory toxicity
        self.substrings = substrings

    def to_ann_lines(self, ann_by_id=None):
        # TODO: substrings
        if ann_by_id is None:
            ann_by_id = {}
        tid = next_id('T', ann_by_id)
        t_ann = '%s\t%s %s %s\t%s' % (
            tid, self.type, self.start, self.end, self.text)
        ann_by_id[tid] = t_ann
        if not self.norm.strip():
            return [t_ann]    # No norm
        else:
            # If the norm ID lacks a namespace, just add something
            nid = next_id('N', ann_by_id)
            norm = self.norm if ':' in self.norm else 'Unknown:%s' % self.norm
            n_ann = '%s\tReference %s %s\t%s' % (nid, tid, norm, self.text)
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
    def __init__(self, id_, text, annotations):
        self.id = id_
        self.text = text
        self.annotations = annotations

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
    return TEXT_RE.match(line.rstrip('\n'))

def is_span_line(line):
    return SPAN_RE.match(line.rstrip('\n'))

def is_rel_line(line):
    return REL_RE.match(line.rstrip('\n'))

def read_pubtator_document(fl):
    """Read from LookaheadIterator, return PubTatorDocument."""
    assert isinstance(fl, LookaheadIterator)
    document_id = None
    document_text = []
    while not fl.lookahead.strip():
        next(fl)    # skip initial empty lines
    for line in fl:
        m = TEXT_RE.match(line.rstrip('\n'))
        if not m:
            raise ParseError('%d: %s' % (fl.index, line))
        docid, type_, text = m.groups()
        if document_id is not None and docid != document_id:
            raise ParseError('%d: %s' % (fl.index, line))
        document_id = docid
        document_text.append(text)
        if not is_text_line(fl.lookahead):
            break

    document_text = '\n'.join(document_text)
    annotations = []
    for line in fl:
        if not line.strip():
            break
        if is_span_line(line):
            annotations.append(SpanAnnotation.from_string(line))
        elif is_rel_line(line):
            annotations.append(RelationAnnotation.from_string(line))
        else:
            raise ParseError('%d: %s' % (fl.index, line))

    return PubTatorDocument(document_id, document_text, annotations)

def read_pubtator(fl):
    """Read PubTator format from file-like object, yield PubTatorDocuments."""
    
    lines = LookaheadIterator(fl)
    while lines:
        yield read_pubtator_document(lines)

def write_standoff(document, options=None):
    try:
        outdir = options.output if options.output is not None else ''
    except:
        outdir = ''
    try:
        encoding = options.encoding
    except:
        encoding = DEFAULT_ENCODING
    textout = path.join(outdir, document.id + '.txt')
    annout = path.join(outdir, document.id + '.ann')
    with codecs.open(textout, 'wt', encoding=encoding) as txt:
        txt.write(document.text)
        if not document.text.endswith('\n'):
            txt.write('\n')
    ann_by_id = {}
    with codecs.open(annout, 'wt', encoding=encoding) as ann:
        for pa_ann in document.annotations:
            if not isinstance(pa_ann, SpanAnnotation):
                warn('not converting %s' % type(pa_ann).__name__)    # TODO
                continue
            for so_ann in pa_ann.to_ann_lines(ann_by_id):
                print >> ann, so_ann

def pubtator_to_standoff(fn, options=None):
    try:
        encoding = options.encoding
    except:
        encoding = DEFAULT_ENCODING
    with codecs.open(fn, 'rU', encoding=encoding) as fl:
        for document in read_pubtator(fl):
            write_standoff(document, options)
        
def main(argv):
    args = argparser().parse_args(argv[1:])

    for fn in args.files:
        pubtator_to_standoff(fn, args)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
