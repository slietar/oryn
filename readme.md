# Oryn

Oryn is a PEP 517-compliant build backend for Python projects.

For now, Oryn only supports pure Python wheels and just recursively copies files from the project root into the wheel, making sure to ignore certain files. It also copies the appropriate metadata from `pyproject.toml` into the wheel's metadata.

Oryn requires Python 3.13 or later.


## Usage

Add the following to your `pyproject.toml`:

```toml
[build-system]
requires = ["oryn"]
build-backend = "oryn"

[tool.oryn]
exclude-git-ignored = true
exclude = [
  # Any patterns here will be excluded from the wheel
  "/dist/",
]
```


## Excluding files

Oryn will exclude the following files and directories from the wheel, with the last taking precedence over the first:

1. Predetermined exclusions.
  - files (not directories) that are immediately in the project root, except for those with `.py` or `.pth` extensions
  - `__pycache__/`
  - `.DS_Store`
  - `.git/`
  - `.gitignore`
  - `.venv/`
  - `*.egg-info/`
2. If the option `tool.oryn.exclude-git-ignored` in `pyproject.toml` is set to `true` (it defaults to `false`), files ignored by Git. Note that this is distinct from files in `.gitignore`, requires a Git directory to be present in the project root directory or one of its ancestors, and the `git` command to be available.
3. Files and directories that correspond to patterns in the `tool.oryn.exclude` option, using [the same pattern format as `.gitignore` files](https://git-scm.com/docs/gitignore#_pattern_format) except for character ranges such as `[a-z]`.

To show which files will be included, install Oryn and run `python -m oryn`.
