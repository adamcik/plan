import os
import re

from compressor import cache
from compressor import filters
from compressor import storage
from compressor.conf import settings

URL_PATTERN = re.compile(r'url\(([^\)]+)\)')


class CssSymlinkAbsoluteFilter(filters.FilterBase):
    """Replaces url() in CSS with hashed symlink. """
    def input(self, filename=None, **kwargs):
        if not filename or not filename.startswith(settings.COMPRESS_ROOT):
            return self.content
        self.directory = os.path.dirname(filename)
        return URL_PATTERN.sub(self.convert, self.content)

    def get_hash(self, filename, length=12):
        mtime = str(cache.get_mtime(filename))
        return cache.get_hexdigest(mtime + filename, length=length)

    def convert(self, match):
        url = match.group(1).strip(' \'"')

        if not url.startswith('..'):  # only handle relative files for now...
            return match.group(0)

        path = os.path.abspath('/'.join([self.directory, url]))
        basename, extension = os.path.splitext(os.path.basename(path))
        basedir = os.path.basename(os.path.dirname(path))

        output = '%s/%s/%s%s' % (settings.COMPRESS_OUTPUT_DIR,
                                 basedir,
                                 self.get_hash(path),
                                 extension)

        output_path = storage.default_storage.path(output)
        output_dir = os.path.dirname(output_path)

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        if not os.path.exists(output_path):
            os.symlink(path, output_path)

        return "url('%s')" % storage.default_storage.url(output)
