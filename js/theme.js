(function () {
  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
  }

  function current() {
    return localStorage.getItem("dagrealtyTheme") || "dark";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var toggle = document.querySelector("[data-theme-toggle]");
    if (!toggle) return;
    toggle.addEventListener("click", function () {
      var next = current() === "dark" ? "light" : "dark";
      localStorage.setItem("dagrealtyTheme", next);
      apply(next);
    });
  });
})();
