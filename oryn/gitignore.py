import re
from dataclasses import dataclass
from os import PathLike
from typing import IO, Sequence


@dataclass(slots=True)
class MatchRule:
  directory: bool
  negated: bool
  pattern: re.Pattern

  def match(self, path: PathLike | str):
    return self.pattern.search(str(path)) is not None

  @classmethod
  def parse(cls, raw_rule: str):
    rule_str = raw_rule

    # TODO: Remove trailing whitespace

    # Check if negated

    negated = rule_str.startswith('!')

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
      absolute = False

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

    if absolute:
      pattern += '^/'
    else:
      pattern += '/'


    index = 0
    escaped = False

    while index < len(rule_str):
      ch = rule_str[index]

      match ch:
        case '\\':
          escaped = True
          continue
        case '*' if (not escaped) and (index + 1 < len(rule_str)) and (rule_str[index + 1] == '*'):
          pattern += '.+'
          index += 1
        case '*' if (not escaped):
          pattern += '[^/]+'
        case '?' if (not escaped):
          pattern += '[^/]'
        case _:
          pattern += re.escape(ch)

      index += 1


    rule = MatchRule(
      directory=directory,
      negated=negated,
      pattern=re.compile(pattern + '$', flags=re.IGNORECASE),
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
  assert str(path)[0] == '/'

  # matched = None

  # for rule in rules:
  #   # if 'dist' in str(path):
  #   #   print(path, rule.match(path), rule.pattern.pattern)

  #   if (rule.negated == matched) and rule.match(path) and ((not rule.directory) or directory):
  #     matched = not rule.negated

  # return matched

  for rule in reversed(rules):
    if rule.match(path) and ((not rule.directory) or directory):
      return not rule.negated

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
