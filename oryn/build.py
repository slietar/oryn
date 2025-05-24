import csv
import re
import shutil
from io import StringIO
from pathlib import Path
from zipfile import ZipFile, ZipInfo

from editables import EditableProject
from packaging.licenses import canonicalize_license_expression
from packaging.version import InvalidVersion, Version

from .inclusion import lookup_file_tree
from .metadata import read_metadata


# See: https://packaging.python.org/en/latest/specifications/name-normalization/#name-normalization
def is_name_valid(unnormalized_name: str, /):
  return re.match(r'^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$', unnormalized_name, re.IGNORECASE) is not None

def normalize_name(name: str, /):
  return re.sub(r'[-_.]+', '-', name).lower()

def process_person_list(person_list: list[str | dict], /):
  names = list[str]()
  emails = list[str]()

  for person in person_list:
    if isinstance(person, str):
      names.append(person)
    elif isinstance(person, dict):
      name = person.get('name', '')
      email = person.get('email', '')

      if email and name:
        emails.append(f'{name} <{email}>')
      elif email:
        emails.append(email)
      elif name:
        names.append(name)

  return names, emails


def write_wheel(wheel_directory: str, /, *, editable: bool = False):
  # Load metadata

  root_path = Path.cwd()

  metadata, tool_metadata = read_metadata(root_path)
  project_metadata = metadata.get('project', {})


  # Normalize name

  unnormalized_name = project_metadata['name']

  if not is_name_valid(unnormalized_name):
    raise ValueError(f'Invalid project name: {unnormalized_name}')

  name = normalize_name(unnormalized_name)


  # Normalize version

  raw_version = project_metadata['version']

  try:
    version = Version(raw_version)
  except InvalidVersion:
    raise ValueError(f'Invalid version: {raw_version}')


  # Write wheel

  snake_name = name.replace('-', '_')
  wheel_file_name = f'{snake_name}-{version}-py3-none-any.whl'

  with ZipFile(Path(wheel_directory) / wheel_file_name, 'w') as archive:
    # Initialize

    # See: https://packaging.python.org/en/latest/specifications/recording-installed-packages/
    dist_info_path = Path(f'{snake_name}-{version}.dist-info')

    record_output = StringIO()
    record_writer = csv.writer(record_output, delimiter=',', lineterminator='\n')

    for record_path in [
      dist_info_path / 'METADATA',
      dist_info_path / 'WHEEL',
      dist_info_path / 'RECORD',
    ]:
      record_writer.writerow([str(record_path), '', ''])

    # Copy targets

    if editable:
      editable_project = EditableProject(name, root_path)

      for item in lookup_file_tree(root_path, tool_metadata):
        if (item is not None) and (item.inclusion_relation == 'target') and (not item.ignored):
          editable_project.map(
            item.path.stem,
            item.path.relative_to(root_path),
          )

      for file_path_str, file_contents in editable_project.files():
        with archive.open(file_path_str, 'w') as file:
          file.write(file_contents.encode())

        record_writer.writerow([file_path_str, '', ''])

      supp_dependencies = list(editable_project.dependencies())
    else:
      for item in lookup_file_tree(root_path, tool_metadata):
        if (item is not None) and (item.inclusion_relative_path is not None) and (not item.ignored) and (not item.is_directory):
          target_path_str = str(item.inclusion_relative_path)
          target_info = ZipInfo(target_path_str)

          # Using this instead of archive.write() to erase timestamp
          with (
            item.path.open('rb') as source_file,
            archive.open(target_info, 'w') as target_file
          ):
            shutil.copyfileobj(source_file, target_file, 1024 * 8)

          record_writer.writerow([target_path_str, '', ''])

      supp_dependencies = []

    # Write metadata, record and wheel files

    with archive.open(str(dist_info_path / 'METADATA'), 'w') as metadata_file:
      # Metadata version

      metadata_file.write(f'Metadata-Version: 2.4\n'.encode())

      # Name and version

      metadata_file.write(f'Name: {name}\n'.encode())
      metadata_file.write(f'Version: {version}\n'.encode())

      # Python version

      if 'requires-python' in project_metadata:
        metadata_file.write(f'Requires-Python: {project_metadata['requires-python']}\n'.encode())

      # Description

      if 'description' in project_metadata:
        metadata_file.write(f'Summary: {project_metadata['description']}\n'.encode())

      # Dependencies

      for dependency in project_metadata.get('dependencies', []) + supp_dependencies:
        metadata_file.write(f'Requires-Dist: {dependency}\n'.encode())

      # Authors

      if 'authors' in project_metadata:
        names, emails = process_person_list(project_metadata['authors'])

        if names:
          metadata_file.write(f'Author: {', '.join(names)}\n'.encode())

        if emails:
          metadata_file.write(f'Author-Email: {', '.join(emails)}\n'.encode())

      # Maintainers

      if 'maintainers' in project_metadata:
        names, emails = process_person_list(project_metadata['maintainers'])

        if names:
          metadata_file.write(f'Maintainer: {', '.join(names)}\n'.encode())

        if emails:
          metadata_file.write(f'Maintainer-Email: {', '.join(emails)}\n'.encode())

      # License

      if 'license' in project_metadata:
        metadata_file.write(f'License-Expression: {canonicalize_license_expression(project_metadata['license'])}\n'.encode())

      # Classifiers

      for classifier in project_metadata.get('classifiers', []):
          metadata_file.write(f'Classifier: {classifier}\n'.encode())

      # Keywords

      keywords = project_metadata.get('keywords', [])

      if keywords:
        metadata_file.write(f'Keywords: {','.join(keywords)}\n'.encode())

      # URLs

      for label, url in project_metadata.get('urls', {}).items():
        metadata_file.write(f'Project-URL: {label}, {url}\n'.encode())

      # Readme

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

        # Write metadata file

        with readme_path.open('rb') as readme_file:
          shutil.copyfileobj(readme_file, metadata_file)

    # with archive.open(str(dist_info_path / 'METADATA'), 'r') as metadata_file:
    #   print(metadata_file.read().decode())

    with archive.open(str(dist_info_path / 'RECORD'), 'w') as record_file:
      record_file.write(record_output.getvalue().encode())

    with archive.open(str(dist_info_path / 'WHEEL'), 'w') as wheel_file:
      wheel_file.write(f'Wheel-Version: 1.0\n'.encode())


    print('-- Wheel contents --------')
    archive.printdir()
    print('--------------------------')


  return wheel_file_name


def build_wheel(wheel_directory: str, config_settings = None, metadata_directory = None):
  return write_wheel(wheel_directory, editable=False)


def build_sdist(sdist_directory, config_settings = None):
  raise NotImplementedError('Sdist building is not implemented yet')


def build_editable(wheel_directory: str, config_settings = None, metadata_directory = None):
  return write_wheel(wheel_directory, editable=True)


__all__ = [
  'build_editable',
  'build_sdist',
  'build_wheel',
]
