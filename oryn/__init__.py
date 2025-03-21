import csv
import re
import shutil
import tomllib
from io import StringIO
from pathlib import Path
from pprint import pprint
from zipfile import Path as ZipInfo
from zipfile import ZipFile

from packaging.version import InvalidVersion, Version

from .util import IgnoreRules, get_ignore_rules, read_metadata


# See: https://packaging.python.org/en/latest/specifications/name-normalization/#name-normalization
def is_name_valid(unnormalized_name: str, /):
  return re.match(r'^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$', unnormalized_name, re.IGNORECASE) is not None

def normalize_name(name: str, /):
  return re.sub(r'[-_.]+', '-', name).lower()


def find_targets(root_path: Path, ignore_rules: IgnoreRules):
  queue = [Path('.')]

  while queue:
    current_relative_path = queue.pop()
    current_path = root_path / current_relative_path

    for child_path in sorted(current_path.iterdir(), key=(lambda path: path.name)):
      is_directory = child_path.is_dir()

      child_relative_path = current_relative_path / child_path.name
      relative_path_test = f'/{child_relative_path}'

      ignored = ignore_rules.match(relative_path_test, directory=is_directory)

      if not ignored:
        if is_directory:
          queue.append(child_relative_path)
        elif child_path.is_file():
          yield child_relative_path


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


  # Find targets

  root_path = Path.cwd()

  _, tool_metadata = read_metadata(root_path)
  ignore_rules = get_ignore_rules(root_path, tool_metadata)


  # Write wheel

  wheel_file_name = f'{name}-{version}-py3-none-any.whl'

  with ZipFile(Path(wheel_directory) / wheel_file_name, 'w') as archive:
    # See: https://packaging.python.org/en/latest/specifications/recording-installed-packages/
    dist_info_path = Path(f'{name}-{version}.dist-info')

    # with ZipPath(archive, str(dist_info_path / 'WHEEL')).open('w') as wheel_file:
    with archive.open(str(dist_info_path / 'WHEEL'), 'w') as wheel_file:
      wheel_file.write(f'Wheel-Version: 1.0\n'.encode())

    with archive.open(str(dist_info_path / 'METADATA'), 'w') as metadata_file:
      metadata_file.write(f'Metadata-Version: 1.0\nName: {name}\nVersion: {version}\n'.encode())

    record_output = StringIO()
    record_writer = csv.writer(record_output, delimiter=',', lineterminator='\n')

    for record_path in [
      dist_info_path / 'METADATA',
      dist_info_path / 'WHEEL',
      dist_info_path / 'RECORD',
    ]:
      record_writer.writerow([str(record_path), '', ''])

    # Copy targets

    for target_path in find_targets(root_path, ignore_rules):
      target_path_str = str(target_path)
      target_info = ZipInfo(target_path_str)

      source_path = root_path / target_path

      # Using this instead of archive.write() to erase timestamp
      with source_path.open('rb') as source_file, archive.open(target_info, 'w') as target_file:
        shutil.copyfileobj(source_file, target_file, 1024 * 8)

      record_writer.writerow([target_path_str, '', ''])

    with archive.open(str(dist_info_path / 'RECORD'), 'w') as record_file:
      record_file.write(record_output.getvalue().encode())


    print('-- Wheel contents --------')
    archive.printdir()
    print('--------------------------')


  return wheel_file_name


def build_sdist(sdist_directory, config_settings=None):
  ...
