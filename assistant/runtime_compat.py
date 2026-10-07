"""Compatibility for six.moves repr used by Qt's signature inspection on Python 3.12."""
import sys


def prepare_six():
    # Optional in source installations; the bundled runtime includes six.
    try:
        import six
        import six.moves
    except ImportError:
        return
    importers = list(sys.meta_path)
    spec = getattr(sys.modules.get('six.moves'), '__spec__', None)
    if spec is not None:
        importers.append(spec.loader)
    for importer in importers:
        if type(importer).__name__ == '_SixMetaPathImporter' and '_path' not in vars(importer):
            # CPython's namespace-module repr accesses loader._path. six uses a
            # synthetic package without a filesystem location; an empty list fits.
            importer._path = []
