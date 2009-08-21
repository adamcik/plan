/*
 * Copyright 2008, 2009 Thomas Kongevold Adamcik
 * 2009 IME Faculty Norwegian University of Science and Technology
 *
 * Code licensed under the Affero GNU General Public License:
 * <http://www.gnu.org/licenses/>
*/

$(function() {
  try { autocomplete_url } catch (e) { autocomplete_url = "" }

  $('#course').autocomplete(autocomplete_url, {
    max: 100,
    minChars: 3,
    multiple: true,
    formatItem: function(row) { return row[0] + ': ' + row[1]},
    formatResult: function(row) { return row[0] },
    width: $('#course').outerWidth()
  });
});
