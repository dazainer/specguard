"""Enumerate mutmut's operators as data inside the isolated image; never import targets."""
import ast
import difflib
import hashlib
import json
import os
from pathlib import Path
import sys

from mutmut import Context, list_mutations, mutate


class IdentifiedContext(Context):
    operator = None

    def should_mutate(self, node):
        selected = super().should_mutate(node)
        if selected:
            self.operator = node.type
        return selected


def main():
    if os.getuid() != 65532 or not Path('/.dockerenv').exists():
        raise SystemExit('Container only')
    records = []
    for relative in sorted(sys.argv[1:]):
        path = Path('/target') / relative
        if not path.resolve().is_relative_to('/target') or not path.is_file():
            raise ValueError('Invalid mutation source')
        original = path.read_text()
        for mutation_id in list_mutations(Context(source=original, filename=relative)):
            context = IdentifiedContext(source=original, filename=relative, mutation_id=mutation_id)
            changed, count = mutate(context)
            if count != 1:
                raise ValueError('Expected exactly one mutmut mutation')
            valid = True
            try:
                ast.parse(changed)
            except SyntaxError:
                valid = False
            diff = ''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True), fromfile=relative, tofile=relative))
            identity = json.dumps([relative, hashlib.sha256(original.encode()).hexdigest(), mutation_id.line_number, mutation_id.index, diff], separators=(',', ':'))
            records.append(dict(id=hashlib.sha256(identity.encode()).hexdigest(), source_file=relative,
                                line=mutation_id.line_number + 1, operator=context.operator,
                                diff=diff, content=changed, valid=valid))
            if len(records) > 1000:
                raise ValueError('Inventory exceeds 1000 mutants; no implicit sampling')
    print(json.dumps(dict(engine='mutmut', version='2.4.4', mutants=records), sort_keys=True))


if __name__ == '__main__':
    main()
