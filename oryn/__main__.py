import os
from dataclasses import KW_ONLY, dataclass, field
from pathlib import Path
from pprint import pprint
from typing import Any, Iterable, Optional

from .gitignore import MatchRule, match_rules, parse_gitignore
from .util import ToolMetadata, read_metadata


ENABLE_COLOR = 'NO_COLOR' not in os.environ

@dataclass(slots=True)
class HierarchyNode:
  value: str
  _: KW_ONLY
  included: bool
  children: 'list[HierarchyNode]' = field(default_factory=list)

  def format(self, *, prefix: str = str()):
    if not self.included:
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


def compute_tree(root_path: Path, tool_metadata: ToolMetadata):
  global_ignore_rules = [MatchRule.parse(r) for r in tool_metadata.get('ignore', [])]
  include_rules = [MatchRule.parse(r, allow_negated=False, enforce_absolute=True) for r in tool_metadata.get('include', [])]

  # abs_root_path = Path('/')

  # queue: list[Optional[tuple[HierarchyNode, Path]]] = [(HierarchyNode('.', included=False), Path('.'))]
  queue: list[Optional[Path]] = [Path('.')]
  ancestor_nodes = list[HierarchyNode]()
  ancestor_ignore_rules = list[list[MatchRule]]()
  inclusion_root: Optional[tuple[Path, int]] = None
  parts = list[str]()

  # from pprint import pprint
  # pprint(include_rules)
  # pprint(global_ignore_rules)

  while queue:
    relative_path = queue.pop()

    if relative_path is None:
      if len(ancestor_nodes) > 1:
        ancestor_nodes.pop()

      if inclusion_root is not None:
        _, depth = inclusion_root

        if depth == len(ancestor_nodes):
          inclusion_root = None

      ancestor_ignore_rules.pop()
      parts.pop()

      continue

    path = root_path / relative_path

    if path.is_dir():
      kind = 'directory'
    elif path.is_file():
      kind = 'file'
    else:
      kind = None


    path_test = f'/{relative_path}'

    if inclusion_root is not None:
      include_match = 'descendant'
    else:
      if ancestor_nodes:
        include_match = match_rules(path_test, include_rules, directory=(kind == 'directory'))
      else:
        include_match = 'ancestor'
      # print('Test', path_test, include_match)

      if include_match == 'target':
        inclusion_root = path, len(ancestor_nodes)
        # print('Found target', path_test, inclusion_root)

    if include_match in ('descendant', 'target'):
      ignored = match_rules(path_test, global_ignore_rules) == 'target'

      if not ignored:
        for ancestor_index, ignore_rules in enumerate(ancestor_ignore_rules, start=1):
          if match_rules('/'.join(parts[ancestor_index:]) + f'/{relative_path.name}', ignore_rules) == 'target':
            ignored = True
            break
    else:
      ignored = False


    node = HierarchyNode(
      (relative_path.name or '.') + ('/' if kind == 'directory' else ''), # + (' [inclusion root]' if kind == 'target' else ''),
      included=(include_match in ('descendant', 'target') and (not ignored)),
    )

    if ancestor_nodes:
      ancestor_nodes[-1].children.append(node)

    ancestor_nodes.append(node)
    parts.append('/' + relative_path.name)
    # print(parts)

    queue.append(None)

    # pprint(include_rules)

    if (kind == 'directory') and (include_match is not None) and (not ignored):
      gitignore_path = path / '.gitignore'

      if gitignore_path.exists():
        with gitignore_path.open('r', encoding='utf-8') as file:
          ancestor_ignore_rules.append(parse_gitignore(file))
      else:
        ancestor_ignore_rules.append([])

      for child_path in reversed(sorted(path.iterdir(), key=(lambda child_path: (child_path.is_dir(), child_path.name)))):
        queue.append(relative_path / child_path.name)
    else:
      ancestor_ignore_rules.append([])


    # print('Q', queue)
    # current_item = queue.pop()

    # if current_item is None:
    #   ancestors.pop()
    #   # path_rules.pop()

    #   if inclusion_root is not None:
    #     _, depth = inclusion_root

    #     if depth == len(ancestors):
    #       inclusion_root = None

    #   continue

    # gitignore_path = root_path / '.gitignore'

    # if gitignore_path.exists():
    #   with gitignore_path.open('r', encoding='utf-8') as file:
    #     dir_rules = parse_gitignore(file)
    # else:
    #   dir_rules = []

    # path_rules.append(dir_rules)


    # current_ancestor, current_path = current_item
    # ancestors.append(current_ancestor)

    # for child_path in sorted((root_path / current_path).iterdir(), key=(lambda path: (path.is_dir(), path.name))):
    #   is_directory = child_path.is_dir()
    #   path_test = f'/{current_path / child_path.name}'

    #   if inclusion_root is not None:
    #     include_match = 'descendant'
    #   else:
    #     include_match = match_rules(path_test, include_rules, directory=is_directory)
    #     # print('Test', path_test, include_match)

    #     if include_match == 'target':
    #       inclusion_root = child_path, len(ancestors)
    #       # print('Found target', path_test, inclusion_root)

    #   print(path_test, include_match)

    #   if include_match in ('descendant', 'target'):
    #     ignored = match_rules(path_test, global_ignore_rules) == 'target'
    #   else:
    #     ignored = False

    #   if is_directory or child_path.is_file():
    #     node = HierarchyNode(
    #       child_path.name + ('/' if is_directory else '') + (' [inclusion root]' if include_match == 'target' else ''),
    #       included=(include_match in ('descendant', 'target') and (not ignored)),
    #     )

    #     ancestors[-1].children.append(node)

    #     if (include_match is not None) and (not ignored) and is_directory:
    #       queue.append(None)
    #       queue.append((node, current_path / child_path.name))

  return ancestor_nodes[0]


if __name__ == '__main__':
  current_path = Path.cwd()

  _, tool_metadata = read_metadata(current_path)

  # from pprint import pprint
  # pprint(ignore_rules)
  # print(MatchRule.parse('__pycache__'))

  print('Files included in the build:')
  root_node = compute_tree(current_path, tool_metadata)
  print(root_node.format())
