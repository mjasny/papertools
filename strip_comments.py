from TexSoup import TexSoup
from TexSoup.utils import TC
from TexSoup.data import TexNode, TexText, TexExpr
import sys
import os


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


if __name__ == '__main__':
    main_file = sys.argv[1]

    abspath = os.path.abspath(main_file)
    dname = os.path.dirname(abspath)
    os.chdir(dname)
    print(f'Working Directory: {dname}')

    # soup = resolve_includes(open_tex(main_file))

    # , skip_envs=('comment', 'lstlisting', ))
    soup = TexSoup(open_tex(main_file))

    print(dir(soup))
    for tex_code in soup:
        if tex_code.category == TC.Comment:
            soup.remove(tex_code)
            print('deleted')
