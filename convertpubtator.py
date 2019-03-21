#!/usr/bin/env python

# Convert PubTator format to other formats.

import sys
import logging

from os import path, makedirs
from errno import EEXIST
from random import random

from pubtator import read_pubtator, SpanAnnotation

logging.basicConfig()
logger = logging.getLogger('convert')
debug, info, warn, error = logger.debug, logger.info, logger.warn, logger.error


DEFAULT_ENCODING = 'utf-8'

FORMATS = ['standoff', 'json', 'oa-jsonld', 'wa-jsonld']
DEFAULT_FORMAT = 'standoff'


def argparser():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('-e', '--encoding', default=DEFAULT_ENCODING,
                    help='Encoding (default {})'.format(DEFAULT_ENCODING))
    ap.add_argument('-f', '--format', default=DEFAULT_FORMAT, choices=FORMATS,
                    help='Output format (default {})'.format(DEFAULT_FORMAT))
    ap.add_argument('-i', '--ids', metavar='FILE', default=None,
                    help='Restrict to documents with IDs in file')
    ap.add_argument('-n', '--no-text', default=False, action='store_true',
                    help='Do not output text files')
    ap.add_argument('-o', '--output', metavar='DIR', default=None,
                    help='Output directory')
    ap.add_argument('-r', '--random', metavar='R', default=None, type=float,
                    help='Sample random subset of documents')
    ap.add_argument('-s', '--subdirs', default=False, action='store_true',
                    help='Create subdirectories by document ID prefix.')
    ap.add_argument('-ss', '--segment', default=False, action='store_true',
                    help='Add sentence segmentation annotations.')
    ap.add_argument('-v', '--verbose', default=False, action='store_true',
                    help='Verbose output')
    ap.add_argument('files', metavar='FILE', nargs='+',
                    help='Input PubTator files')
    return ap


def encoding(options):
    try:
        return options.encoding
    except:
        return DEFAULT_ENCODING


def safe_makedirs(path):
    """Create directory path if it doesn't already exist."""
    # From http://stackoverflow.com/a/5032238
    try:
        makedirs(path)
    except OSError as e:
        if e.errno != EEXIST:
            raise


def output_filename(document, suffix, options):
    try:
        outdir = options.output if options.output is not None else ''
    except:
        outdir = ''
    if options is not None and options.subdirs:
        outdir = path.join(outdir, document.id[:4])
    if outdir != '':
        safe_makedirs(outdir)
    return path.join(outdir, document.id + suffix)


def write_text(document, options=None):
    if options is not None and options.no_text:
        return
    textout = output_filename(document, '.txt', options)
    with open(textout, 'w', encoding=encoding(options)) as txt:
        txt.write(document.text)
        if not document.text.endswith('\n'):
            txt.write('\n')


def write_standoff(document, options=None):
    write_text(document, options)
    annout = output_filename(document, '.ann', options)
    ann_by_id = {}
    with open(annout, 'w', encoding=encoding(options)) as ann:
        for pa_ann in document.annotations:
            try:
                for so_ann in pa_ann.to_ann_lines(ann_by_id):
                    print(so_ann, file=ann)
            except NotImplementedError as e:
                warn('not converting {}'.format(type(pa_ann).__name__))


def write_json(document, options=None):
    write_text(document, options)
    outfn = output_filename(document, '.json', options)
    with open(outfn, 'w', encoding=encoding(options)) as out:
        out.write(document.to_json())


def write_oa_jsonld(document, options=None):
    write_text(document, options)
    outfn = output_filename(document, '.jsonld', options)
    with open(outfn, 'w', encoding=encoding(options)) as out:
        out.write(document.to_oa_jsonld())


def write_wa_jsonld(document, options=None):
    write_text(document, options)
    outfn = output_filename(document, '.jsonld', options)
    with open(outfn, 'w', encoding=encoding(options)) as out:
        out.write(document.to_wa_jsonld())


def add_sentences(document, text=None, base_offset=0):
    from ssplit import sentence_split

    if text is None:
        text = document.text
        base_offset = 0

    if text and not text.isspace():
        split = sentence_split(text)
        assert ''.join(split) == text
        o = 0
        for s in split:
            t = s.rstrip()    # omit trailing whitespace
            from_ = base_offset + o
            to = base_offset + o + len(t)
            span = SpanAnnotation(document.id, from_, to, t, 'sentence')
            document.annotations.append(span)
            o += len(s)

    return document


def segment(document):
    title, tiab = document.title, document.text
    if title and not title.isspace():
        span = SpanAnnotation(document.id, 0, len(title), title, 'title')
        document.annotations.append(span)
    abstract = tiab[len(title)+1:]    # +1 for separating whitespace
    assert title == tiab[:len(title)]
    add_sentences(document, title, 0)
    add_sentences(document, abstract, len(title)+1)
    return document


def convert(fn, writer, options=None):
    i = 0
    with open(fn, 'rU', encoding=encoding(options)) as fl:
        for i, document in enumerate(read_pubtator(fl, options.ids), start=1):
            if i % 100 == 0:
                info('Processed {} documents ...'.format(i))
            if options.random is not None and random() > options.random:
                continue    # skip
            if options.segment:
                segment(document)
            writer(document, options)
    info('Done, processed {} documents.'.format(i))


def read_id_list(fn):
    with open(fn) as f:
        return [l.rstrip('\n') for l in f.readlines()]


def main(argv):
    args = argparser().parse_args(argv[1:])
    if args.verbose:
        logger.setLevel(logging.INFO)
        set_log_level(logging.INFO)
    if args.ids:
        args.ids = set(read_id_list(args.ids))
    if args.random is not None and (args.random < 0 or args.random > 1):
        raise ValueError('must have 0 < ratio < 1')

    if args.format == 'standoff':
        writer = write_standoff
    elif args.format == 'json':
        writer = write_json
    elif args.format == 'oa-jsonld':
        writer = write_oa_jsonld
    elif args.format == 'wa-jsonld':
        writer = write_wa_jsonld
    else:
        raise ValueError('unknown format {}'.format(args.format))

    for fn in args.files:
        convert(fn, writer, args)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
