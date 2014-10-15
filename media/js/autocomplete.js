/* This file is part of the plan timetable generator, see LICENSE for details. */

// TODO: see if http://caniuse.com/#feat=datalist can be used or a simpler pure js one

$(function() {
  var course = $('#course');
  course.autocomplete(course.attr('data-autocomplete'), {
    maxItemsToShow: 100,
    minChars: 3,
    showResult: function(code, name) { return code + ': ' + name},
    useDelimiter: ', ',
  });
});
