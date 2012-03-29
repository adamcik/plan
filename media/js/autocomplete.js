/* This file is part of the plan timetable generator, see LICENSE for details. yy*/

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
