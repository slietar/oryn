import csv
import re
import shutil
import tomllib
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Optional
from zipfile import ZipFile, ZipInfo

from packaging.version import InvalidVersion, Version

from .inclusion import lookup_file_tree
from .gitignore import MatchRule
from .util import ToolMetadata, read_metadata


# See: https://packaging.python.org/en/latest/specifications/name-normalization/#name-normalization
def is_name_valid(unnormalized_name: str, /):
  return re.match(r'^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$', unnormalized_name, re.IGNORECASE) is not None

def normalize_name(name: str, /):
  return re.sub(r'[-_.]+', '-', name).lower()


@dataclass(slots=True)
class Ancestor:
  ignore_rules: list[MatchRule]
  included: bool
  part: str

def find_targets(root_path: Path, tool_metadata: ToolMetadata):
  for item in lookup_file_tree(root_path, tool_metadata):
    if (item is not None) and (item.inclusion_relation in ('descendant', 'target')) and (not item.ignored) and (not item.is_directory):
      yield item.path, item.inclusion_relative_path


def build_wheel(wheel_directory: str, config_settings = None, metadata_directory = None):
  # Load config (TODO: find real name)

  with (Path.cwd() / 'pyproject.toml').open('rb') as config_file:
    config = tomllib.load(config_file)

  project_config = config['project']


  # Normalize name

  unnormalized_name = project_config['name']

  if not is_name_valid(unnormalized_name):
    raise ValueError(f'Invalid project name: {unnormalized_name}')

  name = normalize_name(unnormalized_name)


  # Normalize version

  raw_version = project_config['version']

  try:
    version = Version(raw_version)
  except InvalidVersion:
    raise ValueError(f'Invalid version: {raw_version}')


  # Load metadata

  root_path = Path.cwd()

  metadata, tool_metadata = read_metadata(root_path)
  project_metadata = metadata.get('project', {})


  # Write wheel

  wheel_file_name = f'{name}-{version}-py3-none-any.whl'

  with ZipFile(Path(wheel_directory) / wheel_file_name, 'w') as archive:
    # Initialize

    # See: https://packaging.python.org/en/latest/specifications/recording-installed-packages/
    dist_info_path = Path(f'{name}-{version}.dist-info')

    # with ZipPath(archive, str(dist_info_path / 'WHEEL')).open('w') as wheel_file:
    record_output = StringIO()
    record_writer = csv.writer(record_output, delimiter=',', lineterminator='\n')

    for record_path in [
      dist_info_path / 'METADATA',
      dist_info_path / 'WHEEL',
      dist_info_path / 'RECORD',
    ]:
      record_writer.writerow([str(record_path), '', ''])

    # Copy targets

    for target_path_in_fs, target_path_in_archive in find_targets(root_path, tool_metadata):
      target_path_str = str(target_path_in_archive)
      target_info = ZipInfo(target_path_str)

      source_path = root_path / target_path_in_fs

      # Using this instead of archive.write() to erase timestamp
      with (
        source_path.open('rb') as source_file,
        archive.open(target_info, 'w') as target_file
      ):
        shutil.copyfileobj(source_file, target_file, 1024 * 8)

      record_writer.writerow([target_path_str, '', ''])

    # Write metadata, record and wheel files

    with archive.open(str(dist_info_path / 'METADATA'), 'w') as metadata_file:
      metadata_file.write(f'Metadata-Version: 1.0\nName: {name}\nVersion: {version}\n'.encode())

      if 'requires-python' in project_metadata:
        metadata_file.write(f'Requires-Python: {project_metadata['requires-python']}\n'.encode())

      if 'description' in project_metadata:
        metadata_file.write(f'Summary: {project_metadata['description']}\n'.encode())

      if 'dependencies' in project_metadata:
        for dependency in project_metadata['dependencies']:
          metadata_file.write(f'Requires-Dist: {dependency}\n'.encode())

      if 'readme' in project_metadata:
        if isinstance(project_metadata['readme'], str):
          readme_path = Path(project_metadata['readme'])
          readme_type = None
        else:
          readme_path = Path(project_metadata['readme']['file'])
          readme_type = project_metadata['readme'].get('content-type')

        if not readme_path.is_absolute():
          readme_path = root_path / readme_path

        if readme_type is None:
          match readme_path.suffix.lower():
            case '.md':
              readme_type = 'text/markdown'
            case '.rst':
              readme_type = 'text/x-rst'
            case _:
              readme_type = 'text/plain'

        metadata_file.write(f'Description-Content-Type: {readme_type}\n\n'.encode())

        with readme_path.open('rb') as readme_file:
          shutil.copyfileobj(readme_file, metadata_file)

    with archive.open(str(dist_info_path / 'METADATA'), 'r') as metadata_file:
      print(metadata_file.read().decode())

    with archive.open(str(dist_info_path / 'RECORD'), 'w') as record_file:
      record_file.write(record_output.getvalue().encode())

    with archive.open(str(dist_info_path / 'WHEEL'), 'w') as wheel_file:
      wheel_file.write(f'Wheel-Version: 1.0\n'.encode())


    print('-- Wheel contents --------')
    archive.printdir()
    print('--------------------------')


  return wheel_file_name


def build_sdist(sdist_directory, config_settings=None):
  ...
