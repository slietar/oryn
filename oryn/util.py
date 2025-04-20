import subprocess
import tomllib
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
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
    '__pycache__/',
    '.DS_Store',
    '.git/',
    '.gitignore',
    '.venv/',
    '*.egg-info/',
  ]
]


type ToolMetadata = dict[str, Any]

def read_metadata(root_path: Path):
  with (root_path / 'pyproject.toml').open('rb') as metadata_file:
    metadata = tomllib.load(metadata_file)

  if ('tool' in metadata) and (TOOL_NAME in metadata['tool']):
    tool_metadata: ToolMetadata = metadata['tool'][TOOL_NAME]
  else:
    tool_metadata: ToolMetadata = {}

  return metadata, tool_metadata
