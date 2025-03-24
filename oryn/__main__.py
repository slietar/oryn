import os
from dataclasses import KW_ONLY, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from .util import IgnoreRules, get_ignore_rules, read_metadata

ENABLE_COLOR = 'NO_COLOR' not in os.environ


@dataclass(slots=True)
class HierarchyNode:
  value: str
  _: KW_ONLY
  ignored: bool
  children: 'list[HierarchyNode]' = field(default_factory=list)

  def format(self, *, prefix: str = str()):
    if self.ignored:
      if ENABLE_COLOR:
        value_prefix = '\033[90m'
        value_suffix = '\033[0m'
      else:
        value_prefix = ''
        value_suffix = ' (ignored)'
    else:
      value_prefix = ''
      value_suffix = ''

    return value_prefix + self.value + value_suffix + ''.join([
      '\n' + prefix
        + ('└── ' if (last := (index == (len(self.children) - 1))) else '├── ')
        + child.format(prefix=(prefix + ('    ' if last else '│   ')))
        for index, child in enumerate(self.children)
    ])


def compute_tree(root_path: Path, ignore_rules: IgnoreRules):
  queue: list[Optional[tuple[HierarchyNode, Path]]] = [(HierarchyNode('.', ignored=False), Path('.'))]
  ancestors = list[HierarchyNode]()

  while queue:
    current_item = queue.pop()

    if current_item is None:
      ancestors.pop()
      continue

    current_ancestor, current_path = current_item
    ancestors.append(current_ancestor)

    for child_path in sorted((root_path / current_path).iterdir(), key=(lambda path: (path.is_dir(), path.name))):
      is_directory = child_path.is_dir()
      relative_path_test = f'/{current_path / child_path.name}'

      ignored = ignore_rules.match(relative_path_test, directory=is_directory)

      if is_directory or child_path.is_file():
        node = HierarchyNode(
          child_path.name + ('/' if is_directory else ''),
          ignored=ignored,
        )

        ancestors[-1].children.append(node)

        if (not ignored) and is_directory:
          queue.append(None)
          queue.append((node, current_path / child_path.name))

  return ancestors[0]


if __name__ == '__main__':
  current_path = Path.cwd()

  _, tool_metadata = read_metadata(current_path)
  ignore_rules = get_ignore_rules(current_path, tool_metadata)

  # from pprint import pprint
  # pprint(ignore_rules)
  # print(MatchRule.parse('__pycache__'))

  print('Files included in the build:')
  root_node = compute_tree(current_path, ignore_rules)
  print(root_node.format())
