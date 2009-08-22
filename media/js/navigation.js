/*
 * Copyright 2008, 2009 Thomas Kongevold Adamcik
 * 2009 IME Faculty Norwegian University of Science and Technology
 *
 * Code licensed under the Affero GNU General Public License:
 * <http://www.gnu.org/licenses/>
*/

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

