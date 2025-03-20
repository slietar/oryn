import os
import subprocess
import tomllib
from dataclasses import KW_ONLY, dataclass, field
from pathlib import Path
from typing import Any, Optional

from .gitignore import MatchRule


ENABLE_COLOR = 'NO_COLOR' not in os.environ

DEFAULT_RULES = [
  MatchRule.parse(r) for r in [
    '*',
    '!*/',
    '!*.py',

    '__pycache__',
    '.DS_Store',
    '.git',
    '.gitignore',
    '.venv',
    '*.egg-info',
  ]
]


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


def find_matching_paths(root_path: Path, ignore_rules: list[MatchRule]):
  queue: list[Optional[tuple[HierarchyNode, Path]]] = [(HierarchyNode('.', ignored=False), Path('.'))]
  ancestors = list[HierarchyNode]()

  while queue:
    current_item = queue.pop()

    if current_item is None:
      ancestors.pop()
      continue

    current_ancestor, current_path = current_item
    ancestors.append(current_ancestor)

    # print('Ancestors', [a.value for a in ancestors])

    for child_path in sorted((root_path / current_path).iterdir(), key=(lambda path: (path.is_dir(), path.name))):
      # print('  ->', child_path)
      is_directory = child_path.is_dir()
      relative_path_test = f'/{current_path / child_path.name}'
      # print('  ->', relative_path_test)

      matched = False

      for rule in ignore_rules:
        if (rule.negated == matched) and rule.match(relative_path_test) and ((not rule.directory) or is_directory):
          matched = not rule.negated

      node = HierarchyNode(
        child_path.name + ('/' if is_directory else ''),
        ignored=matched,
      )

      ancestors[-1].children.append(node)

      if (not matched) and is_directory:
        queue.append(None)
        queue.append((node, current_path / child_path.name))

  return ancestors[0]


def find_git_ignored_paths(root_path: Path):
  # See: https://git-scm.com/docs/git-status#_short_format
  process = subprocess.run(['git', 'status', '--ignored', '--short'], cwd=root_path, capture_output=True, text=True)
  print(process.stderr)

  if process.returncode != 0:
    raise ValueError('Failed to run git status:', process.stderr)

  # untracked = list[Path]()
  ignored = list[str]()

  for line in process.stdout.splitlines():
    path = line[3:]

    match line[:2]:
      case '!!':
        ignored.append(path)
      # case '??':
      #   untracked.append(path)
      case _:
        pass

  return ignored


if __name__ == '__main__':
  current_path = Path.cwd()

  with (current_path / 'pyproject.toml').open('rb') as metadata_file:
    metadata = tomllib.load(metadata_file)

  if ('tool' in metadata) and ('oryn' in metadata['tool']):
    tool_metadata: dict[str, Any] = metadata['tool']['oryn']
  else:
    tool_metadata = {}

  match tool_metadata.get('mode', 'default'):
    case 'default':
      ignore_rules = DEFAULT_RULES
    case 'gitignore':
      ignore_rules = [MatchRule.parse('.git')] + [MatchRule.parse('/' + p) for p in find_git_ignored_paths(current_path)]
    case _:
      raise ValueError('Invalid mode:', tool_metadata['mode'])

  if 'ignore' in tool_metadata:
    ignore_rules += [MatchRule.parse(r) for r in tool_metadata['ignore']]


  # from pprint import pprint
  # pprint(ignore_rules)
  # print(MatchRule.parse('__pycache__'))

  print('Files included in the build:')
  root_node = find_matching_paths(current_path, ignore_rules)
  print(root_node.format())
