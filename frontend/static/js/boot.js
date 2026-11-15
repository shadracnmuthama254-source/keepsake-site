// Runs in <head> before the page paints, so there is no flash of the wrong theme.
(function () {
  "use strict";
  var root = document.documentElement;
  root.className = root.className.replace("no-js", "js");

  var KEY = "keepsake-theme";
  var dark = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function saved() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function remember(value) { try { localStorage.setItem(KEY, value); } catch (e) { /* private mode: fine */ } }

  function apply(theme) {
    root.setAttribute("data-theme", theme);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) { meta.setAttribute("content", theme === "dark" ? "#0c0918" : "#faf6ef"); }
    var button = document.querySelector("[data-theme-toggle]");
    if (button) { button.setAttribute("aria-pressed", theme === "dark" ? "true" : "false"); }
  }

  // Saved choice wins; otherwise follow the device.
  var first = saved();
  apply(first === "dark" || first === "light" ? first : (dark && dark.matches ? "dark" : "light"));

  // Keep the button's state right once it exists.
  document.addEventListener("DOMContentLoaded", function () { apply(root.getAttribute("data-theme")); });

  // Switch themes (works anywhere on the page via the data attribute).
  document.addEventListener("click", function (event) {
    var button = event.target.closest ? event.target.closest("[data-theme-toggle]") : null;
    if (!button) { return; }
    var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    if (!reduce) {
      root.classList.add("theme-anim");
      setTimeout(function () { root.classList.remove("theme-anim"); }, 600);
    }
    apply(next);
    remember(next);
  });

  // Until the visitor picks a theme, follow their device if it changes.
  if (dark && dark.addEventListener) {
    dark.addEventListener("change", function (event) {
      var s = saved();
      if (s !== "dark" && s !== "light") { apply(event.matches ? "dark" : "light"); }
    });
  }
})();
