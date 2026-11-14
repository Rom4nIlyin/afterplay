"""Resolve source, legacy portable and organized portable locations."""
from pathlib import Path


def install_root(source):
    source = Path(source).resolve()
    if source.name == 'app' and (source / 'runtime/python313._pth').is_file():
        return source.parent
    return source


def component(root, name):
    root = Path(root)
    if (root / 'app/app.py').is_file():
        return root / 'app' / name
    return root / name


def catalog(root):
    return component(root, 'SHA256SUMS.json')
