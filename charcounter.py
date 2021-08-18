#!/usr/bin/env python3

import sys
import os
import time
import functools
import re


def watch(filename, cb):
    last_mtime = None
    while True:
        stat = os.stat(filename)
        if last_mtime != stat.st_mtime:
            last_mtime = stat.st_mtime
            cb(filename, stat.st_mtime)

        time.sleep(1)
        

def count_char(limit, filename, mtime):
    content = open(filename, 'r').read()
    chars = len(content)

    print('\n'*5)

    if chars <= limit:
        print(f'#chars: {chars}<={limit}')
        print(f'All good characters left: #chars={limit-chars}')
    else:
        print(f'#chars: {chars}>{limit}')
        print(f'Overflow #chars={chars-limit}:')
        print()
        print(content[limit:])

    #print(repr(content))
    m = re.findall(r'\s{2,}$', content, flags=re.MULTILINE)
    if m:
        trailing_whitespaces = sum(len(x)-1 for x in m)
        print(f'Trailing whitespace #char={trailing_whitespaces}')


    
    

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f'Usage: {sys.argv[0]} <filename> <limit>')
        sys.exit(1)

    filename = sys.argv[1]
    limit = int(sys.argv[2])

    try:
        watch(filename, functools.partial(count_char, limit))
    except KeyboardInterrupt:
        pass
