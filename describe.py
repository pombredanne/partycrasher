#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from __future__ import print_function, unicode_literals, division

"""
Print descriptive statistics over launchpad data.
"""

import os
import sys
import json
import csv

from collections import namedtuple, defaultdict, Counter
from itertools import islice, tee

import six
from six import iterkeys, itervalues, iteritems
from six.moves import zip as izip
from six.moves import cPickle as pickle

import regex


def dbg(message, **kwargs):
    ITALIC = "\x1b[3m"
    YELLOW = "\x1b[33m"
    RESET = "\x1b[m"
    print(ITALIC, YELLOW, six.text_type(message).format(**kwargs), RESET,
          file=sys.stderr, sep='')


def bigrams(seq):
    """
    >>> list(bigrams(range(4)))
    [(0, 1), (1, 2), (2, 3)]

    """
    first, second = tee(seq, 2)
    second = islice(second, 1, None)
    return izip(first, second)


class Crash(namedtuple('Crash', 'id stack context')):
    @classmethod
    def new(cls, report_id):
        return cls(report_id, [], {})

    @classmethod
    def parse(cls, report_id, raw_crash):
        crash = cls.new(report_id)
        stack = raw_crash.pop('stacktrace', [])
        crash.stack.extend(StackFrame.parse(frame) for frame in stack)
        crash.context.update(raw_crash)
        return crash

    @property
    def has_recursion(self):
        """
        >>> crash = Crash.new('0')
        >>> crash.stack.append(StackFrame.of(function='main'))
        >>> crash.has_recursion
        False

        >>> crash.stack.append(StackFrame.of(function='init'))
        >>> crash.has_recursion
        False

        >>> crash = Crash.new('1')
        >>> crash.stack.append(StackFrame.of(function='log'))
        >>> crash.stack.append(StackFrame.of(function='fib'))
        >>> crash.stack.append(StackFrame.of(function='fib'))
        >>> crash.stack.append(StackFrame.of(function='main'))
        >>> crash.has_recursion
        True

        """
        return self.max_recursion_depth > 0


    @property
    def max_recursion_depth(self):
        recursion_depth = [0]

        for a, b in bigrams(self.stack):
            saw_recursion = False
            if a.function:
                if a.function == b.function:
                    recursion_depth[-1] += 1
                    saw_recursion = True

            if not saw_recursion and recursion_depth[-1] > 0:
                #dbg("Recursion in {crash}: {func}", crash=self.id, func=a.function)
                recursion_depth.append(0)

        return max(recursion_depth)

    def tokenize(self, tokenizer):
        # From stack trace
        tokens = [token for frame in self.stack
                  for token in frame.tokenize(tokenizer)]

        # From context
        for field in itervalues(self.context):
            tokens.extend(tokenizer(field))

        return tokens



frame_fields = 'module function arguments filename line_number address'


class StackFrame(namedtuple('StackFrame', frame_fields)):
    @classmethod
    def of(cls, **kwargs):
        return StackFrame(module=kwargs.get('module', ''),
                          function=kwargs.get('function', ''),
                          arguments=kwargs.get('arguments', ''),
                          filename=kwargs.get('filename', ''),
                          line_number=kwargs.get('line_number', ''),
                          address=kwargs.get('address', ''))

    @classmethod
    def parse(cls, raw_frame):
        return cls(module=raw_frame.get('dylib', ''),
                   function=raw_frame.get('function', ''),
                   arguments=raw_frame.get('args', ''),
                   filename=raw_frame.get('file', ''),
                   line_number='',
                   address=raw_frame.get('address', ''))

    def tokenize(self, tokenizer):
        tokens = []
        tokens.extend(tokenizer(self.module))
        tokens.extend(tokenizer(self.function))
        tokens.extend(tokenizer(self.arguments))
        tokens.extend(tokenizer(self.filename))
        tokens.extend(tokenizer(self.line_number))
        tokens.extend(tokenizer(self.address))
        return tokens


class Bucket(object):
    def __init__(self, bucket_id):
        self.id = bucket_id
        self.crashes = {}

    def add(self, report_id, crash):
        assert isinstance(crash, Crash)
        self.crashes[report_id] = crash

    def __len__(self):
        return len(self.crashes)

    def __contains__(self, key):
        if isinstance(self, crash):
            for other in iteritem(self.crashes):
                if other is crash:
                    return True
            return False
        else:
            return key in self.crashes


class Corpus(namedtuple('Corpus', 'name crashes buckets')):
    @classmethod
    def new(cls, name):
        return cls(name, {}, {})

    def add_to_bucket(self, report_id, bucket_id):
        if bucket_id not in self.buckets:
            self.buckets[bucket_id] = Bucket(bucket_id)
        bucket = self.buckets[bucket_id]
        bucket.add(report_id, self.crashes[report_id])


class Distribution(object):
    """
    A distribution.
    """
    def __init__(self, label):
        self.label = label

    @property
    def mean(self):
        raise NotImplementedError

    @property
    def mode(self):
        raise NotImplementedError

    def __str__(self):
        return unicode(self).encode("utf-8")


class OrdinalDistribution(Distribution):
    """
    A distribution of ordinal data (e.g., recursion_depth).
    """
    def __init__(self, label):
        super(OrdinalDistribution, self).__init__(label)
        self.counter = Counter()

    def __iadd__(self, thing):
        self.counter[thing] += 1
        return self

    def save_observations(self, basename, key_label="key", amount_label="value"):
        with open(basename+'.csv', 'wb') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow((key_label, amount_label))
            for key in self.counter.elements():
                writer.writerow((key, '1'))

    @property
    def max(self):
        key = max(iterkeys(self.counter))
        return key, self.counter[key]

    @property
    def min(self):
        key = min(iterkeys(self.counter))
        return key, self.counter[key]

    @property
    def mean(self):
        return sum(iterkeys(self.counter)) / len(self)

    @property
    def mode(self):
        return self.counter.most_common(n=1)[0]

    def __len__(self):
        return sum(itervalues(self.counter))

    def __unicode__(self):
        return (
            "{label}:\n"
            "\tMin:\t{min[0]} × {min[1]}\n"
            "\tMax:\t{max[0]}  × {max[1]}\n"
            "\tMode:\t{mode[0]} × {mode[1]}\n"
            "\tMean:\t{mean}"
        ).format(label=self.label,
                 min=self.min,
                 max=self.max,
                 mean=self.mean,
                 mode=self.mode)


class PatternTokenizer(object):
    """
    >>> lerch('a little bit of tea') == ['little']
    True
    >>> camel('XmlHttpRequest') == ['Xml', 'Http', 'Request']
    True

    """
    def __init__(self, pattern, transform=None,
                 min_length=None, max_length=None):
        self.pattern = regex.compile(pattern, regex.VERSION1)
        self.min = min_length or 0
        self.max = max_length or float('infinity')
        self.transform = transform or (lambda x: x)

    def __call__(self, string):
        tokens = self.pattern.splititer(self.transform(string))
        min_len = self.min
        max_len = self.max
        return [token for token in tokens
                if token and min_len <= len(token) <= max_len]


# From ES Docs: https://github.com/elastic/elasticsearch/blob/1.6/docs/reference/analysis/analyzers/pattern-analyzer.asciidoc
# 2016-01-27
camel = PatternTokenizer(
    '([^\\p{L}\\d]+)|'
    '(?<=\\D)(?=\\d)|'
    '(?<=\\d)(?=\\D)|'
    '(?<=[\\p{L}&&[^\\p{Lu}]])(?=\\p{Lu})|'
    '(?<=\\p{Lu})(?=\\p{Lu}[\\p{L}&&[^\\p{Lu}]])'
)
lerch = PatternTokenizer('\W+',
                         transform=six.text_type.lower,
                         min_length=4,
                         max_length=2000)
space = PatternTokenizer('\s+')


def mtime(filename):
    try:
        return os.stat(filename).st_mtime
    except OSError:
        return -float('inf')


def load_from_json():
    dbg("Parsing JSON...")

    with open('lp.json', 'r') as jsonfile:
        database = json.load(jsonfile)

    # Maps id-> { database_id, bucket }
    oracle = database['oracle']
    # Maps id -> { stacktrace, others }
    raw_crashes = database['crashes']

    corpus = Corpus.new('launchpad')

    dbg("Parsing crashes...")
    for dbid, crash_data in iteritems(raw_crashes):
        corpus.crashes[dbid] = Crash.parse(dbid, crash_data)

    dbg("Figuring out buckets...")
    for report_id, info in iteritems(oracle):
        assert report_id == info['database_id']
        bucket_id = info['bucket']
        corpus.add_to_bucket(report_id, bucket_id)

    with open('lp.corpus', 'wb') as picklefile:
        pickle.dump(corpus, picklefile)

    return corpus


def load_from_pickle():
    dbg("Loading from pickle...")
    with open('lp.corpus', 'rb') as picklefile:
        return pickle.load(picklefile)


def load():
    if mtime('lp.json') > mtime('lp.corpus'):
        return load_from_json()
    return load_from_pickle()


def lazy_setdefault(d, k, fn):
    return d[k] if k in d else d.setdefault(k, fn())


# Collect means and totals (modes are trivial!)
#  - per field
#  - per bucket
#  - per report
#  - per corpus
#
# - Unique tokens [fbrc]
# - Tokens per crash [bc]
# - How many context fields? [r]
# - Stack depth [r]
# - Distribution of tokens [fbbc]
#
if __name__ == '__main__':
    corpus = load()
    dbg("Corpus loaded!")

    print("# crashes:", len(corpus.crashes))
    print("# buckets:", len(corpus.buckets))

    dist = OrdinalDistribution('Max recursion depth per crash (corpus-wide)')
    field_dists = {}

    for report_id, crash in iteritems(corpus.crashes):
        # Report recursion depth.
        dist += crash.max_recursion_depth

        # Figure out raw stats on token length.
        for field, value in iteritems(crash.context):
            when_new = lambda: OrdinalDistribution('Raw number of tokens in '+ str(field))
            field_dist = lazy_setdefault(field_dists, field, when_new)
            field_dist += len(camel(value))

    # Print recursion depth.
    print(unicode(dist))
    crashes_with_recursion = sum(amount for value, amount in dist.counter.items() if value > 0)
    dist.save_observations("recursion", key_label="max.depth")

    print()

    # Print token information for each field.
    for dist in itervalues(field_dists):
        print(dist)