/* This file is part of the plan timetable generator, see LICENSE for details. */

(function() {
  function init() {
    document.removeEventListener('DOMContentLoaded', arguments.callee, false);

    for (var group of document.querySelectorAll('[data-toggle-container]')) {
      group.style.display = 'block';
      group.querySelectorAll('[data-toggle]').forEach(toggle => {
        toggle.style.cursor = 'pointer';
        toggle.addEventListener('click', ((inputs, event) => {
          inputs.forEach(input => {
            const targetState = event.target.dataset.toggle == "true";
            if (input.checked != targetState) {
              input.click();
            }
          });
        }).bind(null, group.querySelectorAll('input[type="checkbox"]')))
      })
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, false);
  } else {
    init();
  }
})();

