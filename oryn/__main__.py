import os
from dataclasses import KW_ONLY, dataclass, field
from pathlib import Path
from typing import Optional

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


@dataclass(kw_only=True, slots=True)
class Ancestor:
  ignore_rules: list[MatchRule]
  included: bool
  node: HierarchyNode
  part: str


def compute_tree(root_path: Path, tool_metadata: ToolMetadata):
  global_ignore_rules = [MatchRule.parse(r) for r in tool_metadata.get('ignore', [])]
  include_rules = [MatchRule.parse(r, allow_negated=False, enforce_absolute=True) for r in tool_metadata.get('include', [])]

  queue: list[Optional[Path]] = [Path('.')]
  ancestors = list[Ancestor]()

  while queue:
    relative_path = queue.pop()

    if relative_path is None:
      if len(ancestors) > 1:
        ancestors.pop()

      continue

    path = root_path / relative_path

    if path.is_dir():
      kind = 'directory'
    elif path.is_file():
      kind = 'file'
    else:
      kind = None


    path_test = f'/{relative_path}'
    parts = [*(ancestor.part for ancestor in ancestors), relative_path.name]

    if not ancestors:
      include_rel = 'ancestor'
    elif ancestors[-1].included:
      include_rel = 'descendant'
    else:
      include_rel = match_rules(path_test, include_rules, directory=(kind == 'directory'))

    if include_rel in ('descendant', 'target'):
      ignored = match_rules(path_test, global_ignore_rules) == 'target'

      if not ignored:
        for ancestor_index, ancestor in enumerate(ancestors, start=1):
          if match_rules('/' + '/'.join(parts[ancestor_index:]), ancestor.ignore_rules) == 'target':
            ignored = True
            break
    else:
      ignored = False


    node = HierarchyNode(
      (relative_path.name or '.') + ('/' if kind == 'directory' else '') + (' [inclusion root]' if include_rel == 'target' else ''),
      included=(include_rel in ('descendant', 'target') and (not ignored)),
    )

    if ancestors:
      ancestors[-1].node.children.append(node)

    if (kind == 'directory') and (include_rel is not None) and (not ignored):
      gitignore_path = path / '.gitignore'

      if gitignore_path.exists():
        with gitignore_path.open('r', encoding='utf-8') as file:
          ignore_rules = parse_gitignore(file)
      else:
        ignore_rules = []

      ancestors.append(
        Ancestor(
          ignore_rules=ignore_rules,
          included=(include_rel in ('descendant', 'target')),
          node=node,
          part=relative_path.name,
        )
      )

      queue.append(None)

      for child_path in reversed(sorted(path.iterdir(), key=(lambda child_path: (child_path.is_dir(), child_path.name)))):
        queue.append(relative_path / child_path.name)

  return ancestors[0].node


if __name__ == '__main__':
  current_path = Path.cwd()

  _, tool_metadata = read_metadata(current_path)

  print('Files included in the build:')
  root_node = compute_tree(current_path, tool_metadata)
  print(root_node.format())
