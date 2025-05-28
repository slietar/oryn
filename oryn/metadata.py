import sys
from pathlib import Path
from typing import Any, TypeAlias

if sys.version_info >= (3, 11):
  import tomllib
else:
  import tomli as tomllib


TOOL_NAME = 'oryn'


ToolMetadata: TypeAlias = dict[str, Any]

def read_metadata(root_path: Path):
  with (root_path / 'pyproject.toml').open('rb') as metadata_file:
    metadata = tomllib.load(metadata_file)

  if ('tool' in metadata) and (TOOL_NAME in metadata['tool']):
    tool_metadata: ToolMetadata = metadata['tool'][TOOL_NAME]
  else:
    tool_metadata: ToolMetadata = {}

  return metadata, tool_metadata
