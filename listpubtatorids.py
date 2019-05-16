#!/usr/bin/env python

# List document IDs appearing in PubTator data.

import os
import sys
import gzip
import logging

from pubtator import read_pubtator


logging.basicConfig()
logger = logging.getLogger('list')
info, warning, error = logger.info, logger.warning, logger.error


DEFAULT_ENCODING = 'utf-8'


def argparser():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('-e', '--encoding', default=DEFAULT_ENCODING,
                    help='Encoding (default {})'.format(DEFAULT_ENCODING))
    ap.add_argument('-l', '--limit', metavar='INT', type=int,
                    help='Maximum number of IDs to output')
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


def process_stream(fn, fl, options):
    if options.limit and process.total_count >= options.limit:
        return 0
    i = 0
    for i, document in enumerate(read_pubtator(fl), start=1):
        if i % 100 == 0:
            info('Processed {} documents ...'.format(i))

        print(document.id)

        process.total_count += 1
        if options.limit and process.total_count >= options.limit:
            break
    info('Completed {}, processed {} documents.'.format(fn, i))
    return i


def process(fn, options=None):
    if not fn.endswith('.gz'):
        with open(fn, encoding=encoding(options)) as f:
            return process_stream(fn, f, options)
    else:
        with gzip.open(fn, mode='rt', encoding=encoding(options)) as f:
            return process_stream(fn, f, options)
process.total_count = 0


def main(argv):
    args = argparser().parse_args(argv[1:])
    if args.verbose:
        logger.setLevel(logging.INFO)
    for fn in args.files:
        process(fn, args)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
