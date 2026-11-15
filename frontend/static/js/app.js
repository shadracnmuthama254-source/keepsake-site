/* Keepsake - small progressive enhancements. The site works without this file;
   it only adds comfort (menus, previews, confirmation dialogs). */
(function () {
  "use strict";

  var doc = document;
  function $(selector, root) { return (root || doc).querySelector(selector); }
  function $all(selector, root) { return Array.prototype.slice.call((root || doc).querySelectorAll(selector)); }

  /* ---------- mobile navigation ---------- */
  var navToggle = $(".nav-toggle");
  var nav = $("#site-nav");
  if (navToggle && nav) {
    navToggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  /* ---------- "+ Add" menu: close on outside click / Escape ---------- */
  $all("details.add-menu").forEach(function (menu) {
    doc.addEventListener("click", function (event) {
      if (!menu.contains(event.target)) { menu.removeAttribute("open"); }
    });
    doc.addEventListener("keydown", function (event) {
      if (event.key === "Escape") { menu.removeAttribute("open"); }
    });
  });

  /* ---------- flash messages ---------- */
  function dismiss(flash) {
    flash.classList.add("is-leaving");
    setTimeout(function () { if (flash.parentNode) { flash.parentNode.removeChild(flash); } }, 250);
  }
  $all(".flash").forEach(function (flash) {
    var close = $(".flash-close", flash);
    if (close) { close.addEventListener("click", function () { dismiss(flash); }); }
    if (!flash.classList.contains("flash-error")) { setTimeout(function () { dismiss(flash); }, 7000); }
  });

  /* ---------- greeting follows the visitor's own clock ---------- */
  var greeting = $("[data-greeting]");
  if (greeting) {
    var hour = new Date().getHours();
    greeting.textContent = hour >= 5 && hour < 12 ? "Good morning"
      : hour >= 12 && hour < 17 ? "Good afternoon"
      : hour >= 17 && hour < 22 ? "Good evening" : "Hello, night owl";
  }

  /* ---------- "Go back" button on error pages ---------- */
  $all("[data-back]").forEach(function (link) {
    link.addEventListener("click", function (event) {
      if (window.history.length > 1) { event.preventDefault(); window.history.back(); }
    });
  });

  /* ---------- confirmation before anything is permanently deleted ---------- */
  var dialog = $("#confirm-dialog");
  doc.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.hasAttribute("data-confirm")) { return; }
    if (form.getAttribute("data-confirmed") === "1") { return; }
    event.preventDefault();
    var message = form.getAttribute("data-confirm");

    if (dialog && typeof dialog.showModal === "function") {
      $("#confirm-message", dialog).textContent = message;
      dialog.returnValue = "";
      var onClose = function () {
        dialog.removeEventListener("close", onClose);
        if (dialog.returnValue === "ok") {
          form.setAttribute("data-confirmed", "1");
          form.submit();
        }
      };
      dialog.addEventListener("close", onClose);
      dialog.showModal();
    } else if (window.confirm(message)) {
      form.setAttribute("data-confirmed", "1");
      form.submit();
    }
  });

  /* ---------- stop double submits (e.g. uploading twice) ---------- */
  doc.addEventListener("submit", function (event) {
    var form = event.target;
    if (event.defaultPrevented || !(form instanceof HTMLFormElement) || !form.hasAttribute("data-busy")) { return; }
    var button = $("button[type=submit]", form);
    if (button) {
      setTimeout(function () { button.disabled = true; button.classList.add("is-busy"); }, 0);
    }
  });
  window.addEventListener("pageshow", function () {
    $all("form[data-busy] button.is-busy").forEach(function (button) {
      button.disabled = false;
      button.classList.remove("is-busy");
    });
  });

  /* ---------- show / hide password ---------- */
  $all("[data-toggle-password]").forEach(function (button) {
    button.addEventListener("click", function () {
      var input = doc.getElementById(button.getAttribute("data-toggle-password"));
      if (!input) { return; }
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      button.textContent = show ? "Hide" : "Show";
      button.setAttribute("aria-label", show ? "Hide password" : "Show password");
    });
  });

  /* ---------- archive filters: apply when a dropdown changes ---------- */
  $all("[data-autosubmit]").forEach(function (control) {
    control.addEventListener("change", function () { if (control.form) { control.form.submit(); } });
  });

  /* ---------- item form ---------- */
  var itemForm = $(".item-form");
  if (itemForm) {
    // Show the fields that fit the chosen type (CSS reads data-type).
    $all("input[name=type]", itemForm).forEach(function (radio) {
      radio.addEventListener("change", function () {
        if (radio.checked) { itemForm.setAttribute("data-type", radio.value); }
      });
    });

    // File: size check + live preview.
    var fileInput = $("input[type=file]", itemForm);
    var previewBox = $("#file-preview");
    var clientError = $("#file-client-error");
    var maxBytes = (parseFloat(itemForm.getAttribute("data-max-mb")) || 15) * 1024 * 1024;
    var previewUrl = null;

    var formatSize = function (bytes) {
      if (bytes < 1024) { return bytes + " B"; }
      if (bytes < 1024 * 1024) { return (bytes / 1024).toFixed(1) + " KB"; }
      return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    };
    var resetPreview = function () {
      if (previewUrl) { URL.revokeObjectURL(previewUrl); previewUrl = null; }
      if (previewBox) { previewBox.hidden = true; $("img", previewBox).hidden = true; }
    };

    if (fileInput) {
      fileInput.addEventListener("change", function () {
        resetPreview();
        if (clientError) { clientError.hidden = true; clientError.textContent = ""; }
        var file = fileInput.files && fileInput.files[0];
        if (!file) { return; }

        if (file.size > maxBytes) {
          fileInput.value = "";
          if (clientError) {
            clientError.textContent = "That file is " + formatSize(file.size) + " - the limit is " + formatSize(maxBytes) + ".";
            clientError.hidden = false;
          }
          return;
        }
        if (previewBox) {
          $(".file-preview__meta", previewBox).textContent = file.name + " · " + formatSize(file.size);
          if (file.type && file.type.indexOf("image/") === 0) {
            previewUrl = URL.createObjectURL(file);
            var image = $("img", previewBox);
            image.src = previewUrl;
            image.hidden = false;
          }
          previewBox.hidden = false;
        }
      });
    }

    // Tag suggestions: click to add to the comma-separated field.
    $all(".tag-suggest [data-tag]", itemForm).forEach(function (button) {
      button.addEventListener("click", function () {
        var input = doc.getElementById("tags");
        if (!input) { return; }
        var current = input.value.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
        var tag = button.getAttribute("data-tag");
        var exists = current.some(function (s) { return s.toLowerCase() === tag.toLowerCase(); });
        if (!exists) { current.push(tag); }
        input.value = current.join(", ");
        input.focus();
      });
    });
  }
})();
