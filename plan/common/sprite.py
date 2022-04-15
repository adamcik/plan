#!/usr/bin/python
# This file is part of the plan timetable generator, see LICENSE for details.

"""Minimal binary to generate and optimize sprites for css."""

from __future__ import absolute_import
from __future__ import print_function
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image
from six.moves import map

BASE_CSS = '''
[class^="%(prefix)s"],
[class*=" %(prefix)s"] {
  display: inline-block;
  width: %(size)spx;
  height: %(size)spx;
  line-height: %(size)spx;
  vertical-align: text-top;
  background: url("%(output)s") no-repeat;
}
'''
BASE_TMPL = '.%(prefix)s%%s { background-position: %%dpx %%dpx; }\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--padding', type=int, default=3)
    parser.add_argument('--size', type=int, default=16, help='Image width and height')
    parser.add_argument('--rows', type=int, default=5, help='Number of rows in grid')
    parser.add_argument('--prefix', default='icon-', help='CSS prefix')
    parser.add_argument('--output', default='sprite.png', help='Output file')
    parser.add_argument('--compress', default='none', choices=('pngcrush', 'optipng', 'none'))
    parser.add_argument('input', nargs='+', help='Input files')

    args = parser.parse_args()

    padding = args.padding
    size = args.size + padding
    rows = args.rows
    output = os.path.abspath(args.output)
    files = list(map(os.path.abspath, args.input))
    grid = []

    context = {'prefix': args.prefix,
               'size': args.size,
               'output': args.output}

    css = BASE_CSS % context
    tmpl = BASE_TMPL % context

    if output in files:
        files.remove(output)

    while files:
        grid.append(files[:rows])
        files = files[rows:]

    width, height = (size*len(grid)-padding, size*rows-padding)
    sprite = Image.new(mode='RGBA', size=(width, height), color=(0,0,0,0))

    for i, row in enumerate(grid):
        for j, path in enumerate(row):
            x, y = i*size, j*size
            sprite.paste(Image.open(path), (x, y))

            name = os.path.splitext(os.path.basename(path))[0]
            css +=  tmpl % (name, -x, -y)

    tmp = tempfile.NamedTemporaryFile(suffix=os.path.splitext(output)[1])
    sprite.save(tmp.name)

    original_size = os.stat(tmp.name).st_size

    if args.compress == 'pngcrush':
        subprocess.call(
            ['pngcrush', '-rem', 'alla' '-reduce', '-brute',
             tmp.name, output])
    elif args.compress == 'optipng':
        if os.path.exists(output):
            os.remove(output)
        subprocess.call(
            ['optipng', '-zc1-9', '-zm1-9', '-zs0-3', '-f0-5', '-o7',
             '-out', output, tmp.name])
    else:
        shutil.copyfile(tmp.name, output)

    final_size = os.stat(output).st_size

    print('/* -- sprite css rules -- */')
    print(css)
    print('/* -- done -- */')

    print('Original size: %s, final size: %s. %.3f%% improvment.' % (
        original_size, final_size, 100 - final_size * 100.0 / original_size))
