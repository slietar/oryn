from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from pprint import pprint
from typing import Literal, Optional
from zipfile import ZipFile, ZipInfo

from packaging.version import InvalidVersion, Version

from .gitignore import MatchRule, match_rules, parse_gitignore
from .util import ToolMetadata, read_metadata


@dataclass(slots=True)
class Ancestor:
  ignore_rules: list[MatchRule]
  included: bool
  part: str

@dataclass(kw_only=True, slots=True)
class Item:
  has_children: bool
  ignored: bool
  include_rel: Literal['ancestor', 'descendant', 'target', None]
  is_directory: bool
  path: Path


def lookup_file_tree(root_path: Path, tool_metadata: ToolMetadata):
  global_ignore_rules = [MatchRule.parse(r) for r in tool_metadata.get('ignore', [])]
  include_rules = [MatchRule.parse(r, allow_negated=False, enforce_absolute=True) for r in tool_metadata.get('include', [])]

  ancestors = list[Ancestor]()
  queue: list[Optional[Path]] = [Path('.')]

  while queue:
    relative_path = queue.pop()

    if relative_path is None:
      ancestors.pop()
      yield None

      continue

    path = root_path / relative_path

    if path.is_dir():
      is_directory = True
    elif path.is_file():
      is_directory = False
    else:
      continue

    path_test = f'/{relative_path}'
    parts = [*(ancestor.part for ancestor in ancestors), relative_path.name]

    if not ancestors:
      include_rel = 'ancestor'
    elif ancestors[-1].included:
      include_rel = 'descendant'
    else:
      include_rel = match_rules(path_test, include_rules, directory=is_directory)

    if include_rel in ('descendant', 'target'):
      ignored = match_rules(path_test, global_ignore_rules) == 'target'

      if not ignored:
        for ancestor_index, ancestor in enumerate(ancestors, start=1):
          if match_rules('/' + '/'.join(parts[ancestor_index:]), ancestor.ignore_rules) == 'target':
            ignored = True
            break
    else:
      ignored = False

    has_children = is_directory and (include_rel is not None) and (not ignored)

    yield Item(
      has_children=has_children,
      ignored=ignored,
      include_rel=include_rel,
      is_directory=is_directory,
      path=path,
    )

    if has_children:
      gitignore_path = path / '.gitignore'

      if gitignore_path.exists():
        with gitignore_path.open() as file:
          ignore_rules = parse_gitignore(file)
      else:
        ignore_rules = []

      ancestors.append(
        Ancestor(
          ignore_rules=ignore_rules,
          included=(include_rel in ('descendant', 'target')),
          part=relative_path.name,
        ),
      )

      queue.append(None)

      for child_path in reversed(sorted(path.iterdir(), key=(lambda child_path: (child_path.is_dir(), child_path.name)))):
        queue.append(relative_path / child_path.name)
