import re
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import IO, Sequence


@dataclass(slots=True)
class MatchRule:
  directory: bool
  exact: bool
  negated: bool
  pattern: re.Pattern
  ancestor_patterns: list[re.Pattern]

  def match(self, path: PathLike | str):
    return self.pattern.search(Path(path).as_posix()) is not None

  def ancestor_match(self, path: PathLike | str):
    path_ = Path(path)

    for ancestor_pattern in self.ancestor_patterns:
      if ancestor_pattern.search(path_.as_posix()):
        return True

    return False

  @classmethod
  def parse(cls, raw_rule: str, *, allow_negated: bool = True, enforce_absolute: bool = False):
    rule_str = raw_rule

    # TODO: Remove trailing whitespace

    # Check if negated

    negated = allow_negated and rule_str.startswith('!')

    if negated:
      rule_str = rule_str[1:]

    # Check if absolute

    if rule_str.startswith('/'):
      absolute = True
      rule_str = rule_str[1:]
    elif rule_str.startswith('\\/'):
      absolute = True
      rule_str = rule_str[2:]
    else:
      absolute = enforce_absolute

    # Check if directory

    if rule_str.endswith('\\/'):
      directory = True
      rule_str = rule_str[:-2]
    elif rule_str.endswith('/'):
      directory = True
      rule_str = rule_str[:-1]
    else:
      directory = False

    # Compute pattern

    pattern = ''
    ancestor_patterns = list[str]()

    if absolute:
      pattern += '^/'
    else:
      pattern += '/'
      ancestor_patterns.append('/')


    exact = True

    index = 0
    escaped = False

    while index < len(rule_str):
      ch = rule_str[index]

      match ch:
        case '\\':
          escaped = True
          continue
        case '*' if (not escaped) and (index + 1 < len(rule_str)) and (rule_str[index + 1] == '*'):
          exact = False
          pattern += '.+'
          index += 1
        case '*' if (not escaped):
          exact = False
          pattern += '[^/]+'
        case '?' if (not escaped):
          exact = False
          pattern += '[^/]'
        case '/':
          exact = True

          if absolute:
            ancestor_patterns.append(pattern)

          pattern += '/'
        case _:
          pattern += re.escape(ch)

      index += 1

    rule = MatchRule(
      directory=directory,
      exact=exact,
      negated=negated,
      pattern=re.compile(pattern + '$', flags=re.IGNORECASE),
      ancestor_patterns=[re.compile(p + '$', flags=re.IGNORECASE) for p in ancestor_patterns],
    )

    return rule


def parse_gitignore(file: IO[str]):
  rules = list[MatchRule]()

  for line in file:
    line = line.strip()

    if not line or line.startswith('#'):
      continue

    rules.append(MatchRule.parse(line))

  return rules


# None = no rule matched
def match_rules(path: PathLike | str, rules: Sequence[MatchRule], *, directory: bool = False):
  path_ = Path(path)
  assert path_.absolute

  for rule in reversed(rules):
    if rule.match(path_) and ((not rule.directory) or directory):
      if rule.negated:
        break

      return 'target'

  for rule in rules:
    if (not rule.negated) and directory and rule.ancestor_match(path_):
      return 'ancestor'

  return None


# print(parse_rule('__pycache__'))
# print(parse_rule('__pycache__/'))
# print(parse_rule('/a/x/c'))
# print(parse_rule('!foo/**/bar'))

# rules = parse_gitignore(StringIO('''
# __pycache__
# '''))

# print(rules)
# print(match(rules, '/__pycache__/foo/bar'))
