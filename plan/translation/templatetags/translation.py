# Copyright 2010 Thomas Kongevold Adamcik

# This file is part of Plan.
#
# Plan is free software: you can redistribute it and/or modify
# it under the terms of the Affero GNU General Public License as
# published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Plan is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Affero GNU General Public License for more details.
#
# You should have received a copy of the Affero GNU General Public
# License along with Plan.  If not, see <http://www.gnu.org/licenses/>.

from django.template import Library, Node, TemplateSyntaxError, Variable
from django.utils.translation import activate, get_language
from django.templatetags.i18n import *

register = Library()

def do_language(parser, token):
    try:
        tag, language = token.contents.split()
    except ValueError:
        raise TemplateSyntaxError
    nodelist = parser.parse(('endlanguage',))
    parser.delete_first_token()
    return LanguageNode(language, nodelist)

class LanguageNode(Node):
    def __init__(self, language, nodelist):
        self.language = Variable(language)
        self.nodelist = nodelist

    def render(self, context):
        language = get_language()
        activate(self.language.resolve(context))
        output = self.nodelist.render(context)
        activate(language)
        return output

register.tag('language', do_language)
register.tag('get_available_languages', do_get_available_languages)
register.tag('get_current_language', do_get_current_language)
register.tag('get_current_language_bidi', do_get_current_language_bidi)
register.tag('trans', do_translate)
register.tag('blocktrans', do_block_translate)
