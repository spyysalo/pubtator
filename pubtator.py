# Support for reading PubTator format.

import re
import json
import itertools

from copy import deepcopy
from collections.abc import Iterator
from logging import warning


# Regular expressions matching PubTator format embedded text, span
# annotation, and relation annotation.

TEXT_RE = re.compile(r'^(\d+)\|(.)\|(.*)$')

SPAN_RE = re.compile(r'^(\d+)\t(\d+)\t(\d+)\t([^\t]+)\t(\S+)\t*(\S*)(?:\t(.*))?\s*$')

REL_RE = re.compile(r'^(\d+)\t(\S+)\t(\S+)\t(\S+)\s*$')

NORM_RE = re.compile(r'[A-Za-z0-9]')


def is_text_line(line):
    return TEXT_RE.match(line.rstrip('\n\r'))

def is_span_line(line):
    return SPAN_RE.match(line.rstrip('\n\r'))

def is_rel_line(line):
    return REL_RE.match(line.rstrip('\n\r'))


class ParseError(Exception):
    pass


class LookaheadIterator(Iterator):
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

    def __next__(self):
        return self.next()    # TODO cleanup

    def __nonzero__(self):
        return self.lookahead is not None

    def __bool__(self):
        return self.lookahead is not None


def next_in_seq(prefix, taken):
    """Return first prefix+str(i) (i=1,2,...) not in taken."""

    for i in itertools.count(1):
        if prefix+str(i) not in taken:
            return prefix+str(i)


def pretty_dumps(obj):
    return json.dumps(obj, sort_keys=True, indent=2, separators=(',', ': '))


class SpanAnnotation(object):
    """PubTator span annotation."""

    def __init__(self, docid, start, end, text, type_, norms=None,
                 substrings=None):
        self.docid = docid
        self.start = int(start)
        self.end = int(end)
        self.text = text
        self.type = type_
        self._norms = norms
        # substrings capture cases such as
        #     2234245	314	341	visual or auditory toxicity	Disease	D014786|D006311	visual toxicity|auditory toxicity
        self.substrings = substrings

    @property
    def norms(self):
        """Return list of IDs normalized to or [None] if none."""
        if self._norms is None or not self._norms.strip():
            return [None]

        norms = []
        for norm in self.split_norm(self._norms, self.type):
            if '(Tax:' in norm:
                norm = self.strip_taxonomy_id(norm)
            if ':' not in norm:
                # no namespace; add a guess
                norm = self.norm_namespace(self.type) + ':' + norm
            norms.append(norm)

        return norms

    def validate(self, doc_text):
        if doc_text[self.start:self.end] != self.text:
            warning(
                'text mismatch: {} in {} ({}-{}): "{}" vs. "{}"'.\
                format(self.type, self.docid, self.start, self.end,
                       doc_text[self.start:self.end], self.text)
            )
        # NOTE: RE.search() instead of RE.match()
        if self._norms and not NORM_RE.search(self._norms):
            raise ValueError(
                'norm value error: {} "{}" in {} ({}-{}): "{}"'.\
                format(self.type, self.text, self.docid, self.start, self.end,
                       self._norms)
            )

    def to_dicts(self):
        d = {
            'start': self.start,
            'end': self.end,
            'text': self.text,
            'type': self.map_to_output_type(self.type),
        }
        dicts = []
        for norm in self.norms:
            c = d.copy()
            if norm:
                c['norm'] = norm
            dicts.append(c)
        return dicts

    def to_oa_jsonld_dicts(self, docurl, idx):
        d = {
            '@type' : self.map_to_output_type(self.type),
            'target' : docurl + '/text#char=%d,%d' % (self.start, self.end),
            'text': self.text,
        }
        dicts = []
        for i, norm in enumerate(self.norms):
            c = d.copy()
            c['@id'] = docurl + '/annotations/%d' % (idx+i)
            if norm:
                c['body'] = norm
            dicts.append(c)
        return dicts

    def to_wa_jsonld_dicts(self, docurl, idx):
        d = {
            'type' : 'Span',
            'target' : docurl + '/text#char=%d,%d' % (self.start, self.end),
            'body': {
                'type': self.map_to_output_type(self.type),
            },
            'text': self.text,
        }
        dicts = []
        for i, norm in enumerate(self.norms):
            c = deepcopy(d)
            c['id'] = docurl + '/ann/%d' % (idx+i)
            if norm:
                c['body']['id'] = norm
            dicts.append(c)
        return dicts

    def to_json(self):
        return pretty_dumps(self.to_dicts())

    def to_oa_jsonld(self, docurl, idx):
        return pretty_dumps(self.to_oa_jsonld_dicts(docurl, idx))

    def to_wa_jsonld(self, docurl, idx):
        return pretty_dumps(self.to_wa_jsonld_dicts(docurl, idx))

    def to_ann_lines(self, ann_by_id=None):
        # TODO: substrings
        if ann_by_id is None:
            ann_by_id = {}
        tid = next_in_seq('T', ann_by_id)
        t_ann = '%s\t%s %s %s\t%s' % (
            tid, self.map_to_output_type(self.type), self.start, self.end,
            self.text)
        ann_by_id[tid] = t_ann
        anns = [t_ann]
        for norm in self.norms:
            if not norm:
                continue
            nid = next_in_seq('N', ann_by_id)
            n_ann = '%s\tReference %s %s\t%s' % (nid, tid, norm, self.text)
            ann_by_id[nid] = n_ann
            anns.append(n_ann)
        return anns

    @classmethod
    def from_string(cls, s):
        m = SPAN_RE.match(s)
        if not m:
            raise ParseError('Failed to parse as span: "%s"' % s)
        return cls(*m.groups())

    @staticmethod
    def norm_namespace(type_):
        """Return namespace for normalizations given annotation type."""

        # prexixes from https://github.com/prefixcommons/biocontext/blob/master/registry/uber_context.jsonld
        # Note: this checks for containment instead of equality to allow
        # for "modified" types like "Species-Nomical".
        if 'Species' in type_:
            return 'NCBITaxon'
        elif 'Gene' in type_:
            return 'NCBIGENE'    # Entrez gene ID
        elif 'Chemical' in type_:
            return 'MESH'
        elif any(t for t in ('DNAMutation', 'ProteinMutation', 'SNP')
                 if t in type_):
            return type_    # see https://github.com/spyysalo/pubtator/issues/4
        else:
            return 'unknown'

    @staticmethod
    def split_norm(norm, type_):
        """Return list of IDs contained in PubTator normalization value."""

        # PubTator data can contain several IDs in its normalization
        # field in forms such as the following:
        #     27086975        1178    1188    SOD1 and 2      Gene    6647;6648
        #     129280  825     847     5-iodo-2'-deoxyuridine  Chemical        MESH:C029954|MESH:D007065
        # However, norm cannot be split on all '|' characters due to e.g.
        #     7564788192200677C-->TDNAMutationc|SUB|C|677|T
        # It appears that '|' is only used as a separator for Chemicals
        # (as of Aug 2017).

        if ';' in norm:
            return norm.split(';')
        elif '|' in norm and type_ == 'Chemical':
            return norm.split('|')
        else:
            return [norm]

    @staticmethod
    def strip_taxonomy_id(norm):
        """Return normalizations without taxonomy ID."""
        # See https://github.com/spyysalo/pubtator/issues/2
        m = re.match(r'^(\d+)\(Tax:\d+\)$', norm)
        if not m:
            raise ValueError('failed to strip taxonomy ID from {}'.format(norm))
        else:
            return m.group(1)

    @staticmethod
    def map_to_output_type(type_):
        """Map PubTator type to converted type."""
        # See https://github.com/spyysalo/pubtator/issues/4
        if type_ in ('DNAMutation', 'ProteinMutation', 'SNP'):
            return 'Mutation'
        else:
            return type_


class RelationAnnotation(object):
    """PubTator binary relation annotation."""

    def __init__(self, docid, type_, arg1, arg2):
        self.docid = docid
        self.type = type_
        self.arg1 = arg1
        self.arg2 = arg2

    def validate(self, doc_text):
        pass    # TODO

    def to_dicts(self):
        raise NotImplementedError()    # TODO

    def to_json(self):
        return pretty_dumps(self.to_dicts())

    def to_ann_lines(self, ann_by_id=None):
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
    """PubTator document with text and annotations."""

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

    def validate(self):
        text = self.text
        for a in self.annotations:
            a.validate(text)

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
            'annotations': sum([ a.to_dicts() for a in self.annotations ], [])
        }

    def text_json(self):
        return pretty_dumps(self.text_dict())

    def ann_json(self):
        return pretty_dumps(self.ann_dict())

    def ann_oa_jsonld(self):
        d, u = [], 'pubmed/' + self.id
        for a in self.annotations:
            d.extend(a.to_oa_jsonld_dicts(u, len(d)))
        return pretty_dumps(d)

    def ann_wa_jsonld(self):
        d, u = [], 'PMID:' + self.id
        for a in self.annotations:
            d.extend(a.to_wa_jsonld_dicts(u, len(d)))
        return pretty_dumps(d)

    def to_json(self):
        d = self.text_dict()
        d.update(self.ann_dict())
        return pretty_dumps(d)

    def to_oa_jsonld(self):
        return self.ann_oa_jsonld()    # TODO: text?

    def to_wa_jsonld(self):
        return self.ann_wa_jsonld()


def skip_pubtator_document(fl, ids):
    """Skip the next document from LookaheadIterator if its ID is not in
    the given list, return whether skipped."""

    if not ids:
        return False

    while fl.lookahead is not None and not fl.lookahead.strip():
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
    if fl.lookahead is None or is_text_line(fl.lookahead):
        return    # already at end or new doc
    for line in fl:
        if fl.lookahead is not None and is_text_line(fl.lookahead):
            break


def read_pubtator_document(fl, validate=True):
    """Read from LookaheadIterator, return PubTatorDocument."""

    assert isinstance(fl, LookaheadIterator)

    document_id = None
    text_sections = []

    while fl.lookahead is not None and not fl.lookahead.strip():
        next(fl)    # skip initial empty lines

    for line in fl:
        m = TEXT_RE.match(line.rstrip('\n\r'))
        if not m:
            raise ParseError('%d: expected text, got: %s' % (fl.index, line))
        docid, type_, text = m.groups()
        if document_id is not None and docid != document_id:
            raise ParseError('%d: doc ID mismatch: %s' % (fl.index, line))
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

    d = PubTatorDocument(document_id, text_sections, annotations)
    if validate:
        d.validate()
    return d


def read_pubtator(fl, ids=None, validate=True):
    """Read PubTator format from file-like object, yield PubTatorDocuments.

    If ids is not None, only return documents whose ID is in ids.
    """

    lines = LookaheadIterator(fl)
    while lines:
        start_line = lines.index+1
        if skip_pubtator_document(lines, ids):
            continue
        try:
            yield read_pubtator_document(lines, validate=validate)
        except Exception as e:
            curr_line = lines.index+1
            warning('Error reading {} (lines {}-{}): {} (skipping...)'.
                    format(fl.name, start_line, curr_line, e))
            read_pubtator.errors += 1
            recover_from_error(lines)
read_pubtator.errors = 0
