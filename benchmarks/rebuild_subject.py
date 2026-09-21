"""Rebuild a reviewed subject's bundle; prints its new pin, never updates a manifest."""
import argparse
from pathlib import Path
import runpy


def rebuild(root):
    module = runpy.run_path(str(Path(__file__).parent / 'subjects/first_subject/rebuild_bundle.py'))
    title = 'Reservation pricing benchmark v1' if root.name == 'first_subject' else f'{root.name} benchmark v1'
    return module['rebuild'](root=root.resolve(), title=title)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('subject', type=Path)
    rebuild(parser.parse_args().subject)
