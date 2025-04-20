from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from .matching import MatchRule, match_rules, parse_gitignore
from .metadata import ToolMetadata


DEFAULT_IGNORE_RULES = [
  MatchRule.parse(r) for r in [
    '__pycache__/',
    '.DS_Store',
    '.git/',
    '.gitignore',
    '.venv/',
    '*.egg-info/',
  ]
]


@dataclass(slots=True)
class Ancestor:
  ignore_rules: list[MatchRule]
  inclusion_root_path: Optional[Path]
  part: str

@dataclass(kw_only=True, slots=True)
class Item:
  has_children: bool
  ignored: bool
  inclusion_relation: Literal['ancestor', 'descendant', 'target', None]
  inclusion_relative_path: Optional[Path]
  is_directory: bool
  path: Path


def lookup_file_tree(root_path: Path, tool_metadata: ToolMetadata):
  global_ignore_rules = DEFAULT_IGNORE_RULES + [MatchRule.parse(r) for r in tool_metadata.get('ignore', [])]
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
      inclusion_relation = 'ancestor'
      inclusion_root_path = None
    elif ancestors[-1].inclusion_root_path is not None:
      inclusion_relation = 'descendant'
      inclusion_root_path = ancestors[-1].inclusion_root_path
    else:
      inclusion_relation = match_rules(path_test, include_rules, directory=is_directory)
      inclusion_root_path = path if inclusion_relation in ('descendant', 'target') else None

    if inclusion_relation in ('descendant', 'target'):
      ignored = match_rules(path_test, global_ignore_rules) == 'target'

      if not ignored:
        for ancestor_index, ancestor in enumerate(ancestors, start=1):
          if match_rules('/' + '/'.join(parts[ancestor_index:]), ancestor.ignore_rules) == 'target':
            ignored = True
            break
    else:
      ignored = False

    has_children = is_directory and (inclusion_relation is not None) and (not ignored)

    yield Item(
      has_children=has_children,
      ignored=ignored,
      inclusion_relation=inclusion_relation,
      inclusion_relative_path=(path.relative_to(inclusion_root_path.parent) if inclusion_root_path is not None else None),
      is_directory=is_directory,
      path=path,
    )

    if has_children:
      if tool_metadata.get('use-gitignore'):
        gitignore_path = path / '.gitignore'

        if gitignore_path.exists():
          with gitignore_path.open() as file:
            ignore_rules = parse_gitignore(file)
        else:
          ignore_rules = []
      else:
        ignore_rules = []

      ancestors.append(
        Ancestor(
          ignore_rules=ignore_rules,
          inclusion_root_path=inclusion_root_path,
          part=relative_path.name,
        ),
      )

      queue.append(None)

      for child_path in reversed(sorted(path.iterdir(), key=(lambda child_path: (child_path.is_dir(), child_path.name)))):
        queue.append(relative_path / child_path.name)
