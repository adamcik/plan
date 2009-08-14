/*
 * Copyright 2008, 2009 Thomas Kongevold Adamcik
 * 2009 IME Faculty Norwegian University of Science and Technology
 *
 *  This file is part of Plan.
 *
 *  Plan is free software: you can redistribute it and/or modify
 *  it under the terms of the Affero GNU General Public License as 
 *  published by the Free Software Foundation, either version 3 of
 *  the License, or (at your option) any later version.
 *
 *  Plan is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  Affero GNU General Public License for more details.
 *
 *  You should have received a copy of the Affero GNU General Public
 *  License along with Plan.  If not, see <http://www.gnu.org/licenses/>.
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

  $('#lectures input[name=exclude]:checked').each(add_hidden_to_lectures);
  $('#lectures input[name=exclude]').click(add_hidden_to_lectures);
  $('#courses input[name=course_remove]:checked').each(add_delete_to_courses);
  $('#courses input[name=course_remove]').click(add_delete_to_courses);
  $('#deadlines input[name=deadline_remove]:checked').each(add_delete_to_deadlines);
  $('#deadlines input[name=deadline_remove]').click(add_delete_to_deadlines);

  $('#change-groups div.groupbox').each(function() {
      var div = $(this);
      var a = $('<a class="tiny">Toggle</a>');

      div.css('position', 'relative')
      a.css({position: 'absolute', top: 0, right: 2, cursor: 'pointer'});

      a.toggle(function() { div.find(':checkbox').removeAttr('checked'); return false; },
               function() { div.find(':checkbox').attr('checked', 'checked'); return false; });

      div.prepend(a);
  })
});
