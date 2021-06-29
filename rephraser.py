from TexSoup import TexSoup
from TexSoup.utils import TC
from TexSoup.data import TexNode, TexText, TexExpr
import sys
import re
import os
import difflib
import requests
import argparse


def open_tex(filename):
    if not filename.endswith('.tex'):
        filename += '.tex'
    print(f'reading: {filename}')
    return open(filename, 'r')


def resolve_includes(tex):
    soup = TexSoup(tex, skip_envs=('comment', 'lstlisting', ))

    CMDS = ['subimport', 'import', 'include', 'input']
    for cmd in CMDS:
        for _input in soup.find_all(cmd):
            filename = ''.join(map(lambda x: x.string, _input.args))

            tex_file = open_tex(filename)
            content = resolve_includes(tex_file).contents
            _input.replace_with(*content)

    return soup


class PonsTranslatorRephraser:
    def __init__(self):
        pass

    def rephrase(self, text):
        trans = self.__translate('en', 'de', sentence)
        altered = self.__translate('de', 'en', trans)
        return altered

    def __translate(self, src, dst, text):
        api_url = 'https://api.pons.com/text-translation-web/v4/translate'
        params = {
            'locale': 'de'
        }
        data = {
            "sourceLanguage": src,
            "targetLanguage": dst,
            "text": text
        }
        r = requests.post(api_url, params=params, json=data)
        try:
            return r.json()['text']
        except KeyError:
            print(r.text())
        return text


def color_diff(diff):
    for line in diff:
        print(repr(line))
        if line.startswith('+ '):
            yield f'\033[92m{line[2:]}\033[0m'
        elif line.startswith('- '):
            yield f'\033[91m{line[2:]}\033[0m'
        elif line.startswith('? '):
            yield f'\033[94m{line}\033[0m'
        else:
            yield line[2:]


def get_sentences(main_file, replace=[], abstract=True, captions=True, sections=True):
    main_file = sys.argv[1]

    abspath = os.path.abspath(main_file)
    dname = os.path.dirname(abspath)
    os.chdir(dname)
    print(f'Working Directory: {dname}')

    soup = resolve_includes(open_tex(main_file))

    s = ''
    if abstract:
        for tex_code in (soup.find('abstract') or []):
            if tex_code.category == TC.Comment:
                continue
            s += str(tex_code)

    # for tex_code in soup.find_all('lstlisting'):
    #     print(tex_code)

    if captions:
        for tex_code in soup.find_all('figure'):
            if tex_code.find_all('caption'):
                s += f'{tex_code.caption.string}\n'
            if tex_code.find_all('subcaption'):
                s += f'{tex_code.subcaption.string}\n'

    if sections:
        for tex_code in (soup.find('document') or []):
            if tex_code.category == TC.Comment:
                continue
            if tex_code.category is None:
                continue

            s += str(tex_code).rstrip()

    repl = [
        ('``', '"'),
        ('\'\'', '"'),
        (r'\%', '%'),
    ]
    repl.extend(replace)
    for m, r in repl:
        s = s.replace(m, r)
    s = s.strip()

    if not s:
        return []

    print(s)

    SPLIT_SENTENCE = r'(?<=[\.:;])\s+(?=[A-Z\()])'
    sentences = re.split(SPLIT_SENTENCE, s)
    return sentences


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-abstract', dest='abstract',
                        action='store_false', default=True, help='Skip abstract.')
    parser.add_argument('--skip-captions', dest='captions',
                        action='store_false', default=True, help='Skip sub(captions) of figures.')
    parser.add_argument('--skip-sections', dest='sections',
                        action='store_false', default=True, help='Skip all sections.')
    parser.add_argument('-r', '--repl', action='append', default=[],
                        help=r'Replace within latex source: -r "\system{}=Test" (multiple)')
    parser.add_argument('main.tex', help='Main file of Latex project.')

    args = parser.parse_args()

    repl = map(lambda x: x.split('='), args.repl)

    sentences = get_sentences(sys.argv[1], replace=repl, abstract=args.abstract,
                              captions=args.captions, sections=args.sections)
    rephraser = PonsTranslatorRephraser()

    i = 0
    while i < len(sentences):
        sentence = sentences[i]

        # sys.stdout.write('\x1b[2J\x1b[H')
        sys.stdout.write('\n'*5)

        print(f'***Original***    Sentence: {i+1}/{len(sentences)}')
        print(sentence)
        print()
        print('***Altered***')
        altered = rephraser.rephrase(sentence)
        print(altered)
        print()

        # print('***Diff***')
        # d = difflib.Differ()
        # print(repr(sentence))
        # print(repr(altered))
        # diff = d.compare(sentence.split(), altered.split())
        # diff = color_diff(diff)
        # print(' '.join(diff))

        search = input()
        if search.startswith('/'):
            term = search[1:]
            for _i, s in enumerate(sentences):
                if term in s:
                    i = _i
                    break
        elif search.startswith(':'):
            try:
                i = int(search[1:])-1
            except ValueError:
                pass
        else:
            i += 1

    print('***Done***')
