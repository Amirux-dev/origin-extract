"""Notation décimale, y compris les nombres complexes copiés par Origin."""
import re

REAL = r'(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?'
SCALAR = re.compile(rf'^[+-]?{REAL}$')
COMPLEX = re.compile(rf'^(?:[+-]?{REAL}\s*[+-]\s*(?:{REAL})?[ij]|[+-]?(?:{REAL})?[ij])$', re.IGNORECASE)


def decimal_text(value, point=True):
    if SCALAR.fullmatch(value) or COMPLEX.fullmatch(value):
        return value.replace(',', '.') if point else value.replace('.', ',')
    return value
