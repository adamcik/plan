/* This file is part of the plan timetable generator, see LICENSE for details. */

// TODO: switch to simpler inlined custom code for this.

$(document).keyup(function(event) {
  if ($(event.target).is(':input')) {
    return true;
  }

  var scroll = $(window).width() < $(document).width();
  var url = null;

  if (event.keyCode == 74 || (!scroll && event.keyCode == 37)) { // j or ←
    url = $('#previous').attr('href');
  } else if (event.keyCode == 75 || (!scroll && event.keyCode == 39)) { // k or →
    url = $('#next').attr('href');
  }

  if (url) {
    document.location = url;
  }
});

