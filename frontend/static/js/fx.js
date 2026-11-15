/* Keepsake - motion & delight. Purely decorative: if this file fails or motion is
   reduced, the site still works exactly the same. */
(function () {
  "use strict";

  var doc = document;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) { return; }

  function $(s, r) { return (r || doc).querySelector(s); }
  function $all(s, r) { return Array.prototype.slice.call((r || doc).querySelectorAll(s)); }

  /* ---------- reveal things as they scroll into view ---------- */
  var REVEALS = [
    [".quick-add__tile", "pop"], [".stat-row li", "pop"], [".section-head, .block > .section-title", ""],
    [".item-card", ""], [".collection-card", "pop"], [".empty-state", ""], [".feature", "pop"],
    [".hero__copy", ""], [".page-head, .page-title", ""], [".filter-bar, .filters", ""]
  ];
  var targets = [];
  REVEALS.forEach(function (pair) {
    var groups = new Map();
    $all(pair[0]).forEach(function (el) {
      if (el.classList.contains("reveal")) { return; }
      var key = el.parentNode;
      var n = groups.get(key) || 0;
      groups.set(key, n + 1);
      el.classList.add("reveal");
      if (pair[1]) { el.classList.add("reveal--" + pair[1]); }
      el.style.setProperty("--d", Math.min(n, 9) * 75 + "ms");
      targets.push(el);
    });
  });

  function show(el) { el.classList.add("in"); }
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { show(entry.target); io.unobserve(entry.target); }
      });
    }, { threshold: 0.1, rootMargin: "0px 0px -4% 0px" });
    targets.forEach(function (el) { io.observe(el); });
    // Safety net: never leave anything hidden (e.g. background tab).
    setTimeout(function () { targets.forEach(show); }, 4000);
  } else {
    targets.forEach(show);
  }

  /* ---------- numbers count up ---------- */
  function countUp(el) {
    var end = parseInt(el.textContent, 10);
    if (!isFinite(end) || end <= 0) { return; }
    var start = null, duration = 1000;
    el.textContent = "0";
    function frame(ts) {
      if (start === null) { start = ts; }
      var p = Math.min((ts - start) / duration, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = String(Math.round(end * eased));
      if (p < 1) { requestAnimationFrame(frame); } else { el.textContent = String(end); }
    }
    requestAnimationFrame(frame);
  }
  var nums = $all(".stat__num");
  if (nums.length && "IntersectionObserver" in window) {
    var numObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { countUp(entry.target); numObserver.unobserve(entry.target); }
      });
    }, { threshold: 0.6 });
    nums.forEach(function (n) { numObserver.observe(n); });
  }

  /* ---------- rotating prompt on the dashboard ---------- */
  var prompt = $("[data-rotate]");
  if (prompt) {
    var lines = (prompt.getAttribute("data-rotate") || "").split("|").filter(Boolean);
    var textEl = $("span", prompt) || prompt;
    var idx = 0;
    if (lines.length > 1) {
      setInterval(function () {
        prompt.classList.add("is-swapping");
        setTimeout(function () {
          idx = (idx + 1) % lines.length;
          textEl.textContent = lines[idx];
          prompt.classList.remove("is-swapping");
        }, 420);
      }, 4800);
    }
  }

  /* ---------- scroll progress bar ---------- */
  var bar = $(".fx-progress");
  if (bar) {
    var ticking = false;
    var update = function () {
      var max = doc.documentElement.scrollHeight - window.innerHeight;
      bar.style.setProperty("--p", max > 0 ? Math.min(window.scrollY / max, 1).toFixed(4) : "0");
      ticking = false;
    };
    window.addEventListener("scroll", function () {
      if (!ticking) { ticking = true; requestAnimationFrame(update); }
    }, { passive: true });
    update();
  }

  /* ---------- confetti ---------- */
  var COLORS = ["#ff6b6b", "#ffc83d", "#3ecfa1", "#4ea8ff", "#9b82ff", "#ff7ab8", "#ff9f5a"];
  function confetti(x, y, count) {
    for (var i = 0; i < (count || 26); i++) {
      var piece = doc.createElement("span");
      piece.className = "fx-confetti";
      var angle = Math.random() * Math.PI * 2;
      var dist = 60 + Math.random() * 150;
      piece.style.left = x + "px";
      piece.style.top = y + "px";
      piece.style.background = COLORS[i % COLORS.length];
      piece.style.setProperty("--dx", Math.cos(angle) * dist + "px");
      piece.style.setProperty("--dy", Math.sin(angle) * dist + 90 + "px");
      piece.style.setProperty("--r", (Math.random() * 720 - 360) + "deg");
      piece.addEventListener("animationend", function (e) { if (e.target.parentNode) { e.target.parentNode.removeChild(e.target); } });
      doc.body.appendChild(piece);
    }
  }
  window.keepsakeConfetti = confetti;

  // Celebrate success messages (e.g. signing in, saving something).
  var success = $(".flash-success .flash-icon");
  if (success) {
    setTimeout(function () {
      var rect = success.getBoundingClientRect();
      confetti(rect.left + rect.width / 2, rect.top + rect.height / 2, 34);
    }, 350);
  }


  /* ---------- cursor spotlight on cards ---------- */
  doc.addEventListener("pointermove", function (event) {
    var card = event.target.closest ? event.target.closest(".item-card, .collection-card, .stat a, .feature") : null;
    if (!card) { return; }
    var rect = card.getBoundingClientRect();
    card.style.setProperty("--mx", (event.clientX - rect.left) + "px");
    card.style.setProperty("--my", (event.clientY - rect.top) + "px");
  }, { passive: true });

  /* ---------- sparkle trail (mouse / trackpad only) ---------- */
  if (window.matchMedia && window.matchMedia("(pointer: fine)").matches) {
    var GLYPHS = ["✦", "✧", "★", "♥", "✿"];
    var last = 0, live = 0;
    doc.addEventListener("mousemove", function (event) {
      var now = Date.now();
      if (now - last < 55 || live > 14) { return; }
      last = now;
      var spark = doc.createElement("span");
      spark.className = "fx-spark";
      spark.textContent = GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
      spark.style.left = event.clientX + 6 + "px";
      spark.style.top = event.clientY + 6 + "px";
      spark.style.color = COLORS[Math.floor(Math.random() * COLORS.length)];
      spark.style.setProperty("--dx", Math.round(Math.random() * 30 - 15) + "px");
      spark.style.setProperty("--dy", Math.round(18 + Math.random() * 22) + "px");
      live++;
      spark.addEventListener("animationend", function () {
        live--;
        if (spark.parentNode) { spark.parentNode.removeChild(spark); }
      });
      doc.body.appendChild(spark);
    }, { passive: true });
  }
})();
