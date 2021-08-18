import sys
import re
import os
import difflib
import requests
import argparse
import deepl
import threading
import queue



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




if __name__ == '__main__':
    rephraser = DeepLRephraser()

    while True:
        sentence = input('> ') 

        #print()
        #print(f'***Original***')
        #print(sentence)
        print()
        print('***Altered***')

        altered = rephraser.rephrase(sentence)
        print(f'> {altered}')
        print()

        print(f'#chars: {len(sentence)} --> {len(altered)}')

        #print('***Diff***')
        #d = difflib.Differ()
        ##print(repr(sentence))
        ##print(repr(altered))
        #diff = d.compare(sentence.split(), altered.split())
        #diff = color_diff(diff)
        #print(' '.join(diff))

