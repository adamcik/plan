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

  var url = null;
  if (event.keyCode == 74) { // j
    url = $('#previous').attr('href');
  } else if (event.keyCode == 75) { // k
    url = $('#next').attr('href');
  }

  if (url) {
    document.location = url;
  }
});

