"""Small, reproducible bilingual TF-IDF vectors; no model/API needed at runtime.

These vectors describe the supplied textbook excerpts and catalog metadata. They
are not acoustic embeddings or invented transcripts. Book/version and unit
constraints are applied before cosine retrieval.
"""
import math
import re
import unicodedata
from collections import Counter

ALGORITHM = 'tfidf-cosine-v1'
STOP_WORDS = frozenset('a an the and or to of in on at for with is are be as by it this that your you i we they from then'.split())


def tokens(text):
    normalized = unicodedata.normalize('NFKC', text).lower().replace('’', "'")
    english = [word for word in re.findall(r"[a-z]+(?:'[a-z]+)?|\d+", normalized)
               if word not in STOP_WORDS]
    chinese = []
    for phrase in re.findall(r'[\u4e00-\u9fff]+', normalized):
        chinese.extend(phrase[i:i + 2] for i in range(max(1, len(phrase) - 1)))
    return english + chinese


def fit_idf(documents):
    counts = Counter(term for document in documents for term in set(tokens(document)))
    size = len(documents)
    return {term: math.log((1 + size) / (1 + count)) + 1 for term, count in counts.items()}


def vectorize(text, idf):
    values = {term: (1 + math.log(count)) * idf[term]
              for term, count in Counter(tokens(text)).items() if term in idf}
    norm = math.sqrt(sum(value * value for value in values.values()))
    return {term: round(value / norm, 9) for term, value in values.items()} if norm else {}


def cosine(left, right):
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(term, 0) for term, value in left.items())
