#!/usr/bin/env python

# Convert PubTator format to other formats.

import os
import sys
import gzip
import logging

from contextlib import contextmanager
from abc import ABC, abstractmethod
from errno import EEXIST
from random import random

from pubtator import read_pubtator, SpanAnnotation


logging.basicConfig()
logger = logging.getLogger('convert')
info, warn, error = logger.info, logger.warning, logger.error

DEFAULT_OUT='converted'

DEFAULT_ENCODING = 'utf-8'

FORMATS = ['standoff', 'json', 'oa-jsonld', 'wa-jsonld']
DEFAULT_FORMAT = 'standoff'


def argparser():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('-D', '--database', default=False, action='store_true',
                    help='Output to SQLite DB (default filesystem)')
    ap.add_argument('-e', '--encoding', default=DEFAULT_ENCODING,
                    help='Encoding (default {})'.format(DEFAULT_ENCODING))
    ap.add_argument('-f', '--format', default=DEFAULT_FORMAT, choices=FORMATS,
                    help='Output format (default {})'.format(DEFAULT_FORMAT))
    ap.add_argument('-i', '--ids', metavar='FILE', default=None,
                    help='Restrict to documents with IDs in file')
    ap.add_argument('-l', '--limit', metavar='INT', type=int,
                    help='Maximum number of documents to output')
    ap.add_argument('-n', '--no-text', default=False, action='store_true',
                    help='Do not output text files')
    ap.add_argument('-o', '--output', default=DEFAULT_OUT,
                    help='Output dir/db (default {})'.format(DEFAULT_OUT))
    ap.add_argument('-O', '--no-output', default=False, action='store_true',
                    help='Suppress output (debugging)')
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


def mkdir_p(path):
    """Create directory path if it doesn't already exist."""
    # From http://stackoverflow.com/a/5032238
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != EEXIST:
            raise


def output_filename(document, suffix, options):
    if options is not None and options.subdirs:
        outdir = document.id[:4]
    else:
        outdir = ''
    return os.path.join(outdir, document.id + suffix)


class WriterBase(ABC):
    """Abstracts over filesystem and DB for output."""
    @abstractmethod
    def open(path):
        pass


class FilesystemWriter(WriterBase):
    def __init__(self, base_dir=None):
        self.base_dir = base_dir
        self.known_directories = set()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    @contextmanager
    def open(self, path):
        if self.base_dir is not None and not os.path.isabs(path):
            path = os.path.join(self.base_dir, path)
        directory = os.path.dirname(path)
        if directory not in self.known_directories:
            mkdir_p(directory)
            self.known_directories.add(directory)
        f = open(path, 'w', encoding='utf-8')
        try:
            yield f
        finally:
            f.close()


class SQLiteFile(object):
    """Minimal file-like object that writes into SQLite DB"""
    def __init__(self, key, db, commit_on_flush=False):
        self.key = key
        self.db = db
        self.commit_on_flush = commit_on_flush
        self.data = []

    def write(self, data):
        self.data.append(data)

    def flush(self):
        self.db[self.key] = ''.join(self.data)
        if self.commit_on_flush:
            self.db.commit()

    def close(self):
        self.flush()
        self.db = None


class SQLiteWriter(WriterBase):
    def __init__(self, dbname, commit_interval=10000):
        self.dbname = dbname
        self.commit_interval = commit_interval
        self.db = None
        self._count = 0

    def commit(self):
        info('Committing {} ...'.format(self.dbname))
        self.db.commit()
        info('Committed {}'.format(self.dbname))

    def __enter__(self):
        try:
            import sqlitedict
        except ImportError:
            error('failed to import sqlitedict; try `pip3 install sqlitedict`')
            raise
        self.db = sqlitedict.SqliteDict(self.dbname, autocommit=False)
        return self

    def __exit__(self, *args):
        self.commit()

    @contextmanager
    def open(self, path):
        # commit_on_flush=True makes this 2x slower
        f = SQLiteFile(path, self.db, commit_on_flush=False)
        try:
            yield f
        finally:
            f.close()
        self._count += 1
        if self.commit_interval and self._count % self.commit_interval == 0:
            self.commit()


def write_text(writer, document, options=None):
    if options is not None and options.no_text:
        return
    textout = output_filename(document, '.txt', options)
    with writer.open(textout) as txt:
        txt.write(document.text)
        if not document.text.endswith('\n'):
            txt.write('\n')


def write_standoff(writer, document, options=None):
    write_text(writer, document, options)
    annout = output_filename(document, '.ann', options)
    ann_by_id = {}
    with writer.open(annout) as ann:
        for pa_ann in document.annotations:
            try:
                for so_ann in pa_ann.to_ann_lines(ann_by_id):
                    print(so_ann, file=ann)
            except NotImplementedError as e:
                warn('not converting {}'.format(type(pa_ann).__name__))
            except Exception as e:
                error('error converting {} in {}: {}({})'.format(
                    type(pa_ann).__name__, document.id,
                    type(e).__name__, str(e)))


def write_json(writer, document, options=None):
    write_text(writer, document, options)
    outfn = output_filename(document, '.json', options)
    with writer.open(outfn) as out:
        out.write(document.to_json())


def write_oa_jsonld(writer, document, options=None):
    write_text(writer, document, options)
    outfn = output_filename(document, '.jsonld', options)
    with writer.open(outfn) as out:
        out.write(document.to_oa_jsonld())


def write_wa_jsonld(writer, document, options=None):
    write_text(writer, document, options)
    outfn = output_filename(document, '.jsonld', options)
    with writer.open(outfn) as out:
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


def convert_stream(fn, fl, writer, write_func, options=None):
    if options.limit and convert.total_count >= options.limit:
        return 0
    i = 0
    for i, document in enumerate(read_pubtator(fl, options.ids), start=1):
        if i % 100 == 0:
            info('Processed {} documents ...'.format(i))
        if options.random is not None and random() > options.random:
            continue    # skip
        if options.segment:
            segment(document)

        if not options.no_output:
            write_func(writer, document, options)

        convert.total_count += 1
        if options.limit and convert.total_count >= options.limit:
            break
    info('Completed {}, processed {} documents.'.format(fn, i))
    return i


def convert(fn, writer, write_func, options=None):
    if not fn.endswith('.gz'):
        with open(fn, encoding=encoding(options)) as f:
            return convert_stream(fn, f, writer, write_func, options)
    else:
        with gzip.open(fn, mode='rt', encoding=encoding(options)) as f:
            return convert_stream(fn, f, writer, write_func, options)
convert.total_count = 0


def read_id_list(fn):
    with open(fn) as f:
        return [l.rstrip('\n') for l in f.readlines()]


def main(argv):
    args = argparser().parse_args(argv[1:])
    if args.verbose:
        logger.setLevel(logging.INFO)
    if args.ids:
        args.ids = set(read_id_list(args.ids))
    if args.random is not None and (args.random < 0 or args.random > 1):
        raise ValueError('must have 0 < ratio < 1')

    if args.format == 'standoff':
        write_func = write_standoff
    elif args.format == 'json':
        write_func = write_json
    elif args.format == 'oa-jsonld':
        write_func = write_oa_jsonld
    elif args.format == 'wa-jsonld':
        write_func = write_wa_jsonld
    else:
        raise ValueError('unknown format {}'.format(args.format))

    name = args.output
    if not args.database:
        Writer = FilesystemWriter
    else:
        Writer = SQLiteWriter
        if not name.endswith('.sqlite'):
            name = name + '.sqlite'

    with Writer(name) as writer:
        for fn in args.files:
            convert(fn, writer, write_func, args)

    print('Done, converted {} ({} errors)'.format(
        convert.total_count, read_pubtator.errors, file=sys.stderr))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
