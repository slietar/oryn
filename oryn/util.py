from dataclasses import dataclass
from os import PathLike
import subprocess
from pathlib import Path
import tomllib
from typing import Any

from .gitignore import MatchRule, match_rules


TOOL_NAME = 'oryn'

def find_git_ignored_paths(root_path: Path, /):
  # See: https://git-scm.com/docs/git-status#_short_format
  process = subprocess.run(['git', 'status', '--ignored', '--short'], cwd=root_path, capture_output=True, text=True)

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


GLOBAL_RULES = [
  MatchRule.parse(r) for r in [
    '/*',
    '!*/',
    '!*.py',
    '!*.pth',
    '.git',
  ]
]

DEFAULT_RULES = [
  MatchRule.parse(r) for r in [
    '__pycache__',
    '.DS_Store',
    '.gitignore',
    '.venv',
    '*.egg-info',
  ]
]


@dataclass(slots=True)
class IgnoreRules:
  gitignored: list[MatchRule]
  explicit: list[MatchRule]

  def match(self, path: PathLike | str, *, directory: bool):
    explicit_matched = match_rules(path, self.explicit, directory=directory)

    if explicit_matched is not None:
      return explicit_matched

    gitignored_matched = match_rules(path, self.gitignored, directory=directory)

    if gitignored_matched:
      return True

    global_matched = match_rules(path, GLOBAL_RULES, directory=directory)
    return bool(global_matched)


def get_ignore_rules(root_path: Path, tool_metadata: dict[str, Any]):
  _, tool_metadata = read_metadata(root_path)

  # ignore_rules = GLOBAL_RULES

  if tool_metadata.get('use-git-ignored'):
    gitignored_rules = [MatchRule.parse('/' + p) for p in find_git_ignored_paths(root_path)]
  else:
    gitignored_rules = DEFAULT_RULES

  if 'ignore' in tool_metadata:
    explicit_rules = [MatchRule.parse(r) for r in tool_metadata['ignore']]
  else:
    explicit_rules = []

  return IgnoreRules(gitignored_rules, explicit_rules)


def read_metadata(root_path: Path):
  with (root_path / 'pyproject.toml').open('rb') as metadata_file:
    metadata = tomllib.load(metadata_file)

  if ('tool' in metadata) and (TOOL_NAME in metadata['tool']):
    tool_metadata: dict[str, Any] = metadata['tool'][TOOL_NAME]
  else:
    tool_metadata = {}

  return metadata, tool_metadata
