from io import StringIO
import re
from dataclasses import dataclass
from os import PathLike
from typing import IO


@dataclass(slots=True)
class MatchRule:
  final: bool
  directory: bool
  negated: bool
  pattern: re.Pattern

  def match(self, path: PathLike | str):
    return self.pattern.search(str(path)) is not None

  @classmethod
  def parse(cls, raw_rule: str):
    absolute = '/' in raw_rule
    negated = raw_rule[0] == '!'

    if negated:
      raw_rule = raw_rule[1:]

    directory = raw_rule.endswith('/')

    if directory:
      raw_rule = raw_rule[:-1]

    pattern = ''

    if absolute:
      pattern += '^/'

      if raw_rule[0] == '/':
        raw_rule = raw_rule[1:]
    else:
      pattern += '/'


    index = 0
    escaped = False

    while index < len(raw_rule):
      ch = raw_rule[index]

      match ch:
        case '\\':
          escaped = True
          continue
        case '*' if (not escaped) and (index + 1 < len(raw_rule)) and (raw_rule[index + 1] == '*'):
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
      final=False,
      negated=negated,
      pattern=re.compile(pattern + '$', flags=re.IGNORECASE),
    )

    return rule

    # if not negated:
    #   alt_rule = Rule(
    #     directory=False,
    #     final=True,
    #     negated=False,
    #     pattern=re.compile(pattern + '/'),
    #   )

    #   return [rule, alt_rule]
    # else:
    #   return [rule]


def parse_gitignore(file: IO[str]):
  rules = list[MatchRule]()

  for line in file:
    line = line.strip()

    if not line or line.startswith('#'):
      continue

    rules.append(MatchRule.parse(line))

  return rules


def match(rules: list[MatchRule], path_like: PathLike | str):
  path = str(path_like)
  assert path[0] == '/'

  for rule in rules:
    if rule.final and rule.match(path):
      return True

  for rule in reversed(rules):
    if (not rule.final) and rule.match(path):
      return not rule.negated

  return False


# print(parse_rule('__pycache__'))
# print(parse_rule('__pycache__/'))
# print(parse_rule('/a/x/c'))
# print(parse_rule('!foo/**/bar'))

# rules = parse_gitignore(StringIO('''
# __pycache__
# '''))

# print(rules)
# print(match(rules, '/__pycache__/foo/bar'))
