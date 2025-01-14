/* This file is part of the plan timetable generator, see LICENSE for details. */

document.addEventListener(
  "keyup",
  function (e) {
    var link,
      inputs = ["INPUT", "TEXTAREA", "BUTTON", "SELECT"],
      scroll =
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth;
    if (inputs.indexOf(event.target.tagName) >= 0) {
      return true;
    }
    if (e.keyCode == 74 || (!scroll && e.keyCode == 37)) {
      // j or ←
      link = document.getElementById("previous");
    } else if (e.keyCode == 75 || (!scroll && e.keyCode == 39)) {
      // k or →
      link = document.getElementById("next");
    }
    if (link && link.href) {
      document.location = link.href;
    }
  },
  false,
);
