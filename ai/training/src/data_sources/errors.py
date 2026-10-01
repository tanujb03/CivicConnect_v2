"""Errors for the real-data acquisition/preparation layer."""
from __future__ import annotations


class DataSourceError(Exception):
    """Base class."""


class TermsNotAccepted(DataSourceError):
    """Dataset terms/licence were not explicitly acknowledged by the operator."""


class SchemaMismatch(DataSourceError):
    """The external file does not have the columns/structure the adapter needs."""


class UnsafeOutputPath(DataSourceError):
    """Refusing to write external-dataset content somewhere it could be committed to git."""


class MappingError(DataSourceError):
    """A taxonomy mapping table is malformed or inconsistent with the taxonomy."""
