#!/usr/bin/env python

import re
import nltk.data


# rarely followed by a sentence split
NS_STRING = [
    'a.k.a.', 'approx.', 'ca.', 'cf.', 'e.g.', 'et al.', 'f.c.', 'i.e.',
    'lit.', 'vol.'
]

# rarely followed by a sentence split if the next character is a number
NS_NUM_STRING = [
    'fig.', 'ib.', 'no.',
]

NS_RE = re.compile(r'(?i)\b((?:' +
                   '|'.join(re.escape(s) for s in NS_STRING) +
                   ')\s*)\n')

NS_NUM_RE = re.compile(r'(?i)\b((?:' +
                       '|'.join(re.escape(s) for s in NS_NUM_STRING) +
                       ')\s*)\n(\d)')

nltk_splitter = nltk.data.load('tokenizers/punkt/english.pickle')


def _realign(sentences, text):
    # return sentences with space fixed so that '\n.join(sentences) == text
    aligned = []
    o = 0
    for i, s in enumerate(sentences):
        aligned.append('')

        # resolve extra initial space, if any
        while text[o] != s[0]:
            if not text[o].isspace():
                # can only align space
                raise ValueError('cannot align:\n\t{}\n\t{}'.format(
                    text[o:o+len(s)], s))
            elif i == 0:
                # first sentence, add space to start of current
                aligned[-1] += text[o]
            else:
                # not first, add space to end of previous
                aligned[-2] += text[o]
            o += 1
            
        if text[o:o+len(s)] == s:
            # fully aligned, resolve fast
            aligned[-1] += s
            o += len(s)
            continue

        # align character by character
        p = 0
        while p < len(s):
            if o < len(text) and text[o] == s[p]:
                aligned[-1] += text[o]
                o += 1
                p += 1
            elif s[p].isspace():
                # remove extra space
                p += 1
            elif text[o].isspace():
                # add missing space
                aligned[-1] += text[o]
                o += 1
            else:
                # can only align space
                raise ValueError('cannot align:\n\t{}\n\t{}'.format(
                    text[o:o+len(s)-p], s[p:]))

    # leftover final space, if any
    while o < len(text):
        if not text[o].isspace():
            raise ValueError('cannot align: {}'.format(text[o:]))
        else:
            aligned[-1] += text[o]
            o += 1
    
    assert ''.join(aligned) == text, 'internal error'
    return aligned


def sentence_split(s):
    split = '\n'.join(nltk_splitter.tokenize(s.strip()))
    split = NS_RE.sub(r'\1 ', split)
    split = NS_NUM_RE.sub(r'\1 \2', split)
    split = split.split('\n')
    split = _realign(split, s)
    return split
