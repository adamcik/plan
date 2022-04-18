/* This file is part of the plan timetable generator, see LICENSE for details. */

(function() {
  var xhr, cache = {};

  function fetch(url, callback) {
    try {
      xhr.abort()
    } catch (e) {}
    xhr = new XMLHttpRequest();
    xhr.onreadystatechange = function() {
      if (this.readyState == 4 && this.status == 200) {
        callback(JSON.parse(this.responseText));
      }
    };
    xhr.open('GET', url, true);
    xhr.setRequestHeader('Accept', 'application/json');
    xhr.send();
  }

  function source(term, callback) {
    term = term.split(/\s*,\s*/).pop().replace(/^\s+|\s+/g, '').toLowerCase();
    var location = document.getElementById('location');
    var query = '?q=' + encodeURIComponent(term) +
                '&l=' + encodeURIComponent(location !== null ? location.value : '');

    if (cache[query]) {
      callback(cache[query]);
    } else if (term.length >= 3) {
      var url = this.selector.getAttribute('data-autocomplete');
      fetch(url + query, function(data) {
        cache[query] = data;
        callback(data);
      });
    }
  }

  function render(item, search) {
    var s = document.createElement('div');
    s.className = 'autocomplete-suggestion';
    s.setAttribute('data-code', item[0]);
    s.setAttribute('data-val', search);
    var b = document.createElement('b');
    b.appendChild(document.createTextNode(item[0]));
    s.appendChild(b);
    s.appendChild(document.createTextNode(': ' + item[1]));
    return s.outerHTML;
  }

  function select(e, term, item) {
    var terms = term.split(/\s*,\s*/);
    terms[terms.length - 1] = item.getAttribute('data-code')
    this.selector.value = terms.join(', ') + ', ';
    e.preventDefault();
    return false;
  }

  function init() {
    document.removeEventListener('DOMContentLoaded', arguments.callee, false);
    new autoComplete({
      selector: document.getElementById('course'),
      minChars: 0,
      cache: false,
      source: source,
      renderItem: render,
      onSelect: select
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, false);
  } else {
    init();
  }
})();
