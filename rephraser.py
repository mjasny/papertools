from TexSoup import TexSoup
from TexSoup.utils import TC
from TexSoup.data import TexNode, TexText, TexExpr
import sys
import re
import os
import difflib
import requests
import argparse
import deepl
import threading
import queue


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


class DeepLRephraser:
    def __init__(self):
        pass

    def rephrase(self, text):
        trans = deepl.translate(source_language="EN",
                                target_language="DE", text=text)
        altered = deepl.translate(
            source_language="DE", target_language="EN", text=trans)
        return altered


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


def p_map(func, data):
    N = len(data)
    result = [None] * N

    def wrapper(i):
        result[i] = func(data[i])

    threads = [threading.Thread(target=wrapper, args=(i,))
               for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    return result


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

    class Rephraser:
        def __init__(self, *, sentences):
            self.sentences = sentences
            self.cache = {}
            self.prefetch_q = queue.Queue()
            self.thread = threading.Thread(target=self.__prefetcher)
            self.__stop = False
            self.thread.start()
            self.rephrasers = [
                DeepLRephraser(),
                # PonsTranslatorRephraser(),
            ]

        def __del__(self):
            self.thread.join()
            self.prefetch_q.put(None)
            self.__stop = True

        def get(self, i):
            if i not in self.cache:
                sentence = self.sentences[i]
                if len(self.rephrasers) == 1:
                    # No thread
                    self.cache[i] = [self.rephrasers[0].rephrase(sentence)]
                else:
                    self.cache[i] = p_map(
                        lambda x: x.rephrase(sentence), self.rephrasers)
            return self.cache[i]

        def prefetch(self, i):
            self.prefetch_q.put(i)

        def __prefetcher(self):
            while not self.__stop:
                i = self.prefetch_q.get()
                try:
                    self.get(i)
                except Exception as e:
                    print(e)
                    continue

    sentences = get_sentences(
        sys.argv[1], replace=repl, abstract=args.abstract, captions=args.captions, sections=args.sections)
    rephraser = Rephraser(sentences=sentences)
    i = 0
    while i < len(sentences):
        sentence = sentences[i]

        # sys.stdout.write('\x1b[2J\x1b[H')
        sys.stdout.write('\n'*5)

        print(f'***Original***    Sentence: {i+1}/{len(sentences)}')
        print(sentence)
        print()
        print('***Altered***')

        for altered in rephraser.get(i):
            print(altered)
            print()
        rephraser.prefetch(i+1)

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
