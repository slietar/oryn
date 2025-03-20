import csv
import re
import tomllib
from io import StringIO
from pathlib import Path
from pprint import pprint
from zipfile import ZipFile

from packaging.version import InvalidVersion, Version

from .gitignore import MatchRule, parse_gitignore


# See: https://packaging.python.org/en/latest/specifications/name-normalization/#name-normalization
def is_name_valid(unnormalized_name: str, /):
  return re.match(r'^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$', unnormalized_name, re.IGNORECASE) is not None

def normalize_name(name: str, /):
  return re.sub(r'[-_.]+', '-', name).lower()


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

  default_rules = [MatchRule.parse(r) for r in [
    '.DS_Store',
    '.git',
    '*.egg-info',
    '.gitignore',
    '/pyproject.toml',
  ]]

  root_path = Path.cwd()
  queue = [root_path]
  current_parts = list[tuple[Path, list[MatchRule]]]()
  targets = list[Path]() # Relative to root_path

  while queue:
    current_path = queue.pop()
    gitignore_path = current_path / '.gitignore'

    # print('+', current_path)

    for part_index in range(len(current_parts) - 1, -1, -1):
      part_path, _ = current_parts[part_index]

      if not part_path in current_path.parents:
        current_parts.pop()
        # print('    Popping:', part_path)

    if gitignore_path.exists():
      with gitignore_path.open() as gitignore_file:
        rules = parse_gitignore(gitignore_file)
        current_parts.append((current_path, rules))
    # else:
    #   rules = []

    for child_path in current_path.iterdir():
      # print('  ->', child_path)

      relative_path = child_path.relative_to(current_path)
      is_directory = child_path.is_dir()

      relative_path_test = '/' + str(relative_path)
      matched = False

      for rule in default_rules:
        if rule.match(relative_path_test) and ((not rule.directory) or is_directory):
          matched = not rule.negated

      for _, part_rules in current_parts:
        for rule in part_rules:
          if rule.match(relative_path_test) and ((not rule.directory) or is_directory):
            matched = not rule.negated

        if matched:
          break

      if matched:
        continue

      if is_directory:
        queue.append(child_path)

      # print('Adding:', child_path)
      targets.append(child_path.relative_to(root_path))

      # with archive.

    # print(current_parts)

  # print('Targets:')
  # pprint(targets)


  # Write wheel

  wheel_file_name = f'{name}-{version}-py3-none-any.whl'

  with ZipFile(Path(wheel_directory) / wheel_file_name, 'w') as archive:
    # See: https://packaging.python.org/en/latest/specifications/recording-installed-packages/
    dist_info_path = Path(f'{name}-{version}.dist-info')
    # archive.mkdir(str(dist_info_path))

    with archive.open(str(dist_info_path / 'WHEEL'), 'w') as wheel_file:
      wheel_file.write(f'Wheel-Version: 1.0\n'.encode())

    with archive.open(str(dist_info_path / 'METADATA'), 'w') as metadata_file:
      metadata_file.write(f'Metadata-Version: 1.0\nName: {name}\nVersion: {version}\n'.encode())

    record_output = StringIO()
    record_writer = csv.writer(record_output, delimiter=',', lineterminator='\n')

    record_paths = [
      dist_info_path / 'METADATA',
      dist_info_path / 'WHEEL',
      dist_info_path / 'RECORD',
    ]

    # Copy targets

    for target_path in targets:
      source_path = root_path / target_path

      # if source_path.is_dir():
      #   pass
      # else:

      # TODO: Maybe erase timestamp
      if source_path.is_file():
        archive.write(source_path, str(target_path))
        record_paths.append(target_path)

      # archive.write(target_path, str(target_path

    for record_path in record_paths:
      record_writer.writerow([str(record_path), '', ''])

    with archive.open(str(dist_info_path / 'RECORD'), 'w') as record_file:
      record_file.write(record_output.getvalue().encode())

    archive.printdir()



  return wheel_file_name


def build_sdist(sdist_directory, config_settings=None):
  ...
