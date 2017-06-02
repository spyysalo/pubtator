#!/usr/bin/env python

# Merge Web Annotation files.

from __future__ import print_function

import os
import sys
import re
import json
import logging
import errno

from collections import defaultdict
from logging import debug, info, warn, error

from webannotation import read_annotations


def pretty_dump(obj, out):
    return json.dump(obj, out, sort_keys=True, indent=2, separators=(',', ': '))


def argparser():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', '--output', metavar='DIR', default=None,
                    help='Output directory')
    ap.add_argument('-r', '--recurse', default=False, action='store_true',
                    help='Recurse into subdirectories')
    ap.add_argument('-s', '--suffix', default='.jsonld',
                    help='Suffix of files to process (with -r)')
    ap.add_argument('-u', '--union', default=False, action='store_true',
                    help='Take union when files are missing (with -r)')
    ap.add_argument('-v', '--verbose', default=False, action='store_true',
                    help='Verbose output')
    ap.add_argument('files', nargs='+', help='Files or directories to merge')
    return ap


def _split_id(id_):
    """Split string into minimal prefix and trailing digits as integer."""
    m = re.match(r'^(.*?)(\d*)$', id_)
    if not m:
        raise ValueError('failed to split ID {}'.format(a.id))
    prefix, num = m.groups()
    if num == '':
        num = 0
    else:
        num = int(num)
    return prefix, num


def resolve_duplicate_ids(annotations):
    """Update IDs in sets of annotations to avoid duplicates in merge."""
    annotations_by_id = defaultdict(list)
    duplicates = set()
    for anns in annotations:
        for a in anns:
            if a.id in annotations_by_id:
                duplicates.add(a)
            annotations_by_id[a.id].append(a)

    # create map to efficiently mint new IDs.
    max_by_id_prefix = defaultdict(int)
    for anns in annotations:
        for a in anns:
            prefix, num = _split_id(a.id)
            max_by_id_prefix[prefix] = max(max_by_id_prefix[prefix], num)
    debug('max_by_id_prefix: {}'.format(dict(max_by_id_prefix)))

    # create mapping to new IDs for each annotation set
    id_maps = []
    for anns in annotations:
        id_map = {}
        for a in anns:
            if a not in duplicates:
                continue
            prefix, _ = _split_id(a.id)
            num = max_by_id_prefix[prefix] + 1
            max_by_id_prefix[prefix] = num
            new_id = prefix+str(num)
            id_map[a.id] = new_id
        id_maps.append(id_map)
    debug('id_maps: {}'.format(id_maps))

    # remap IDs
    for anns, id_map in zip(annotations, id_maps):
        for a in anns:
            a.remap_ids(id_map)


def mkdir_p(path):
    if path in mkdir_p.made:
        return
    # from https://stackoverflow.com/a/600612
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise
    mkdir_p.made.add(path)
mkdir_p.made = set()


def output_annotations(annotations, files, relative_path, options=None):
    annotations = [a.to_dict() for a in annotations]
    if options is None or not options.output:
        pretty_dump(annotations, sys.stdout)
    else:
        bn = os.path.basename(files[0])
        dn = os.path.join(options.output, relative_path)
        fn = os.path.join(dn, bn)
        mkdir_p(dn)
        with open(fn, 'w') as out:
            pretty_dump(annotations, out)


def merge_files(files, relative_path='', options=None):
    annotations = []
    for fn in files:
        try:
            annotations.append(read_annotations(fn))
        except Exception, e:
            error('failed to parse {}: {}'.format(fn, e))
            raise

    resolve_duplicate_ids(annotations)

    merged = [a for anns in annotations for a in anns]

    output_annotations(merged, files, relative_path, options)


def merge_directories(dirs, relative_path='', options=None):
    dir_files = [os.listdir(d) for d in dirs]

    # filter to files/directories to consider for merge
    dir_filtered = []
    for d, df in zip(dirs, dir_files):
        filtered = []
        for f in df:
            p = os.path.join(d, f)
            if os.path.isdir(p):
                if options and options.recurse:
                    filtered.append(f)
                else:
                    info('skipping dir {} (consider --recurse)'.format(p))
            elif os.path.isfile(p):
                _, ext = os.path.splitext(os.path.basename(p))
                if options is None or ext == options.suffix:
                    filtered.append(f)
                else:
                    debug('skipping file {} (--suffix parameter)'.format(p))
        dir_filtered.append(filtered)
    dir_files = [set(fs) for fs in dir_filtered]

    union = set.union(*dir_files)
    intersection = set.intersection(*dir_files)

    if union == intersection:
        files = union
    elif options and options.union:
        files = union
        # Support for --union will require the rest of the code to
        # allow for the possiblity of missing files and directories and
        # treat these as empty sets of annotations and files, resp.
        raise NotImplementedError('--union')
    else:
        skipped = sorted(list(union-intersection))
        if len(skipped) < 10:
            skiptxt = ' '.join(skipped)
        else:
            skiptxt = '{} ...'.format(' '.join(skipped[:10]))
        warn('skipping {} non-overlapping files (consider --union): {}'.format(
            len(skipped), skiptxt))
        files = intersection

    info('processing {} files in {}'.format(len(files), ' '.join(dirs)))

    for f in files:
        paths = [os.path.join(d, f) for d in dirs]
        merge(paths, options, relative_path, recursed=True)


def merge(paths, options=None, relative_path='', recursed=False):
    files = [p for p in paths if os.path.isfile(p)]
    dirs = [p for p in paths if os.path.isdir(p)]
    missing = [p for p in paths if not os.path.exists(p)]
    other = [p for p in paths if p not in files and p not in dirs]

    # sanity checks
    if missing:
        raise IOError('no such file or directory: {}'.format(
            ' '.join(other)))
    elif other:
        raise ValueError('neither file or directory: {}'.format(
            ' '.join(other)))
    elif files and dirs:
        raise ValueError('mix of files ({}) and directories ({})'.format(
            ' '.join(files), ' '.join(dirs)))

    assert (files and not dirs) or (dirs and not files), 'internal error'

    if files:
        return merge_files(files, relative_path, options)
    else:
        assert dirs
        if recursed and (options is None or not options.recurse):
            warn('nor recursing into {} (consider --recurse)'.format(
                ' '.join(dirs)))
        else:
            if recursed:
                bn = os.path.basename(dirs[0])
                relative_path = os.path.join(relative_path, bn)
            return merge_directories(dirs, relative_path, options)


def main(argv):
    args = argparser().parse_args(argv[1:])
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    if len(args.files) < 2:
        error('need at least two files or directories to merge')
        return 1
    merge(args.files, args)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
