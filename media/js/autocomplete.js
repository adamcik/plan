/* This file is part of the plan timetable generator, see LICENSE for details. */

$(function() {
  var course = $('#course');
  course.autocomplete(course.attr('data-autocomplete'), {
    max: 100,
    minChars: 3,
    multiple: true,
    formatItem: function(row) { return row[0] + ': ' + row[1]},
    formatResult: function(row) { return row[0] },
    width: course.outerWidth()
  });
});
