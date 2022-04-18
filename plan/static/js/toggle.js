/* This file is part of the plan timetable generator, see LICENSE for details. */

(function() {
  function init() {
    document.removeEventListener('DOMContentLoaded', arguments.callee, false);
    var groups = document.querySelectorAll('#change-groups .groupbox'),
        template = document.getElementById('toogle-template'),
        wrapper, inputs;

    var toggle = function(state) {
      for (var j=0; j < this.length; j++) {
        if (state) {
          this[j].setAttribute('checked', 'checked');
        } else {
          this[j].removeAttribute('checked');
        }
      }
    };

    for (var i=0; i < groups.length; i++) {
      inputs = groups[i].querySelectorAll('input');
      wrapper = template.cloneNode(true);
      wrapper.removeAttribute('id');
      wrapper.removeAttribute('style');
      wrapper.querySelector('.toogle-all').addEventListener(
        'click', toggle.bind(inputs, true));
      wrapper.querySelector('.toogle-none').addEventListener(
        'click', toggle.bind(inputs, false));

      groups[i].querySelector('strong').parentNode.appendChild(wrapper);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, false);
  } else {
    init();
  }
})();

