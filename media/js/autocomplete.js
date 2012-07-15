/* This file is part of the plan timetable generator, see LICENSE for details. */

$(function() {
  var course = $('#course');
  course.autocomplete(course.attr('data-autocomplete'), {
    maxItemsToShow: 100,
    minChars: 3,
    showResult: function(code, name) { return code + ': ' + name},
    useDelimiter: ', ',
  });
});
