from enum import Enum
from re import match, compile

import argparse
from platform import system
from subprocess import Popen, PIPE

VERSION_REGEX = r'(\d+\.)?(\d+\.)?(\d+\.)?(\*|\d+)'
PATTERN = compile(r'''((?:[^\s"']|"[^"]*"|'[^']*')+)''')


class Bump(Enum):
    major = 0
    minor = 1
    patch = 2


def _run_cmd(cmd):
    print(cmd)
    print()

    output, error = Popen(PATTERN.split(cmd)[1::2], stdout=PIPE, stderr=PIPE).communicate()

    if error.decode('utf-8').strip():
        print('    ' + error.decode('utf-8').strip())

    return output.decode('utf-8').strip(), error.decode('utf-8').strip()


def get_latest_version():
    p = Popen(['git', 'ls-remote', '--tags'], stdout=PIPE, stderr=PIPE)

    output, error = p.communicate()

    if error and not error.decode('utf-8').strip() == 'From ssh://git@github.com/worgarside/wg-utilities.git':
        exit(error.decode('utf-8'))

    tags = [line.split('\t')[1].replace('refs/tags/', '') for line in output.decode('utf-8').split('\n')
            if 'refs/tags' in line and not line.endswith('^{}')]

    releases = [tag for tag in tags if match(VERSION_REGEX, tag)]

    return sorted(releases, reverse=True)[0]


def new_version(latest_version):
    version_digits = latest_version.split('.')

    version_digits[Bump[args.bump].value] = str(int(version_digits[Bump[args.bump].value]) + 1)

    for digit in range(Bump[args.bump].value + 1, len(version_digits)):
        version_digits[digit] = '0'

    return '.'.join(version_digits)


def create_release_branch(old, new):
    _run_cmd('git push --all origin')
    _run_cmd(f'git flow release start {new}')

    with open('setup.py', 'r') as f:
        setup_file = f.readlines()

    version_line_num, version_line_content = [(index, line) for index, line in enumerate(setup_file) if
                                              line.strip().lower().startswith('version=')][0]

    setup_file[version_line_num] = version_line_content.replace(old, new)

    with open('setup.py', 'w') as f:
        f.writelines(setup_file)

    _run_cmd(f'git add setup.py')
    _run_cmd(f'git commit -m "vb {new}"')
    if not system() == 'Windows':
        _run_cmd(f'git tag -a {new} -m ""')
    _run_cmd(f'git flow release finish {new}')
    _run_cmd(f'git push')
    _run_cmd(f'git push --tags')
    _run_cmd(f'git push origin master:master')
    _run_cmd(f'pipenv run build')
    _run_cmd(f'pipenv run deploy')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bump')
    args = parser.parse_args()

    try:
        Bump[args.bump]
    except KeyError:
        raise KeyError(f"'{args.bump}' is not a valid bump type")

    lv = get_latest_version()

    create_release_branch(lv, new_version(lv))