// Small page behaviours. Kept in a file, not inline, so the Content Security Policy holds.
(function () {
  "use strict";

  // Open the Report an issue dialog once HTMX has loaded the form into it.
  document.addEventListener("htmx:afterSwap", function (event) {
    if (event.detail.target.id !== "issue-dialog-body") return;
    var dialog = document.getElementById("issue-dialog");
    if (dialog && !dialog.open) dialog.showModal();
    showFieldsForType(event.detail.target);
  });

  document.addEventListener("click", function (event) {
    var close = event.target.closest("[data-close-dialog]");
    if (close) close.closest("dialog").close();
  });

  // Fields such as "steps to reproduce" only apply to some issue types.
  function showFieldsForType(root) {
    var checked = root.querySelector("input[name='type']:checked");
    var type = checked ? checked.value : "";
    root.querySelectorAll("[data-show-for]").forEach(function (group) {
      group.hidden = group.dataset.showFor.split(" ").indexOf(type) === -1;
    });
  }

  document.addEventListener("change", function (event) {
    if (event.target.name === "type") showFieldsForType(event.target.closest("form"));
  });

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form.issue-form").forEach(showFieldsForType);
  });
})();
