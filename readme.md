# Oryn

Oryn is a PEP 517-compliant build backend for Python projects.

For now, Oryn only supports pure Python wheels and just recursively copies files from the project root into the wheel, making sure to ignore certain files. It also copies the appropriate metadata from `pyproject.toml` into the wheel's metadata.

Oryn requires Python 3.13 or later.


## Usage

Add the following to your `pyproject.toml`:

```toml
[build-system]
requires = ["oryn~=1.0"]
build-backend = "oryn"

[tool.oryn]
# src layout
include = ["/src/foo/"]
include = ["/src/*/"]

# flat layout
include = ["/foo/"]

ignore = [
  "*.pyc",
]

use-gitignore = true
```

The following files are ignored by default:

- `__pycache__/`
- `.DS_Store`
- `.git/`
- `.gitignore`
- `.venv/`
- `*.egg-info/`

To show which files will be included, install Oryn and run `python -m oryn`.
