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

  function normalize(value) {
    return value.trim().toLowerCase();
  }

  function init() {
    document.removeEventListener('DOMContentLoaded', arguments.callee, false);
    attach('#courses input[name="course_remove"]', 'course', 'delete');
    attach('#lectures input[name="exclude"]', 'lecture', 'hide');

    document.querySelectorAll('[data-toggle-container]').forEach(container => {
      const filter = container.querySelector('[data-filter]')
      const rows = [...container.querySelectorAll('tbody tr')];

      const keys = [...container.querySelector('thead tr').children].map((th, index) =>
        th.dataset.search ?? null
      );

      const data = rows.map(tr =>
        [...tr.children].map((child, index) =>
          keys[index] !== null ? normalize(child.textContent) : ''
        ).filter(d => d.length > 0)
      );

      const update = () => {
        const needle = normalize(filter.value).split(/\s+/).filter(n => n.length > 0);

        const result = data.map((d, index) => {
          return needle.every(n => d.some(v => v.includes(n))) ? index : null;
        });

        rows.forEach((tr, index) => tr.hidden = !(needle.length == 0 || result.includes(index)));
      }

      filter.addEventListener('input', update);
      filter.addEventListener('keydown', event => {
        if (event.key === "Escape" || (event.key == "c" && event.ctrlKey)) {
          filter.value = '';
          update();
        }
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, false);
  } else {
    init();
  }
})();
