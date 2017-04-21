#!/usr/bin/env python

# Convert PubTator format to other formats.

import sys
import codecs

from os import path, makedirs
from errno import EEXIST
from logging import warn

from pubtator import read_pubtator


DEFAULT_ENCODING = 'utf-8'

FORMATS = ['standoff', 'json', 'oa-jsonld', 'wa-jsonld']
DEFAULT_FORMAT = 'standoff'


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
    ap.add_argument('-s', '--subdirs', default=False, action='store_true',
                    help='Create subdirectories by document ID prefix.')
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
            try:
                for so_ann in pa_ann.to_ann_lines(ann_by_id):
                    print >> ann, so_ann
            except NotImplementedError, e:
                warn('not converting %s' % type(pa_ann).__name__)


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
    i = 0
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
