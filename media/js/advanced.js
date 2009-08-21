/*
 * Copyright 2008, 2009 Thomas Kongevold Adamcik
 * 2009 IME Faculty Norwegian University of Science and Technology
 *
 * Code licensed under the Affero GNU General Public License:
 * <http://www.gnu.org/licenses/>
*/

(function() {
  function add_hidden_to_lectures() {
      var input = $(this);

      if (input.is(':checked')) {
          $('.lecture-' + input.val()).addClass('hide');
      } else {
          $('.lecture-' + input.val()).removeClass('hide');
      }
  };

  function add_delete_to_courses() {
      var input = $(this);

      if (input.is(':checked')) {
          $('.course-' + input.val()).addClass('delete');
      } else {
          $('.course-' + input.val()).removeClass('delete');
      }
  };

  function add_delete_to_deadlines() {
      var input = $(this);

      if (input.is(':checked')) {
          $('.deadline-' + input.val()).addClass('delete');
      } else {
          $('.deadline-' + input.val()).removeClass('delete');
      }
  }

  function add_toggle() {
    var div = $(this);
    var a = $('<a class="tiny">Toggle</a>');

    div.css('position', 'relative')
    a.css({position: 'absolute', top: 0, right: 2, cursor: 'pointer'});

    a.toggle(function() { div.find(':checkbox').removeAttr('checked'); return false; },
             function() { div.find(':checkbox').attr('checked', 'checked'); return false; });

    div.prepend(a);
  }

  $(function() {
    $('#lectures input[name=exclude]:checked').each(add_hidden_to_lectures);
    $('#lectures input[name=exclude]').click(add_hidden_to_lectures);
    $('#courses input[name=course_remove]:checked').each(add_delete_to_courses);
    $('#courses input[name=course_remove]').click(add_delete_to_courses);
    $('#deadlines input[name=deadline_remove]:checked').each(add_delete_to_deadlines);
    $('#deadlines input[name=deadline_remove]').click(add_delete_to_deadlines);
    $('#change-groups div.groupbox').each(add_toggle)
  });
})();
