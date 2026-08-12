(function () {
  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    document.querySelectorAll("[data-theme-set]").forEach(function (btn) {
      var active = btn.getAttribute("data-theme-set") === theme;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function current() {
    return localStorage.getItem("dagrealtyTheme") || "dark";
  }

  document.addEventListener("DOMContentLoaded", function () {
    apply(current());
    document.querySelectorAll("[data-theme-set]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var next = btn.getAttribute("data-theme-set");
        localStorage.setItem("dagrealtyTheme", next);
        apply(next);
      });
    });
  });
})();
