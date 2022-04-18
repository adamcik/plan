/* This file is part of the plan timetable generator, see LICENSE for details. */

// TODO: use http://www.hunlock.com/blogs/Totally_Pwn_CSS_with_Javascript instead

(function() {
  function attach(selector, type, action) {
    var func, inputs = document.querySelectorAll(selector);
    for (var i=0; i < inputs.length; i++) {
      func = toggle.bind(inputs[i], '.' + type + '-' + inputs[i].value, action);
      inputs[i].addEventListener('change', func, false);
      func();
    }
  }

  function toggle(selector, klass) {
    var targets = document.querySelectorAll(selector);
    for (var i=0; i < targets.length; i++) {
      if (this.checked) {
        targets[i].classList.add(klass);
      } else {
        targets[i].classList.remove(klass);
      }
    }
  }

  function init() {
    document.removeEventListener('DOMContentLoaded', arguments.callee, false);
    attach('#courses input[name="course_remove"]', 'course', 'delete');
    attach('#lectures input[name="exclude"]', 'lecture', 'hide');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, false);
  } else {
    init();
  }
})();
