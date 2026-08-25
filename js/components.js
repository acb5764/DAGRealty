(function () {
  var NAV_LINKS = [
    { href: "index.html", label: "Home" },
    { href: "listings.html", label: "Listings" },
    { href: "about.html", label: "About" },
    { href: "contact.html", label: "Contact" },
  ];

  function currentPage() {
    var path = window.location.pathname.split("/").pop();
    return path === "" ? "index.html" : path;
  }

  class SiteHeader extends HTMLElement {
    connectedCallback() {
      var page = currentPage();
      var navHtml = NAV_LINKS.map(function (link) {
        var current = link.href === page ? ' aria-current="page"' : "";
        return '<a href="' + link.href + '"' + current + ">" + link.label + "</a>";
      }).join("");

      this.innerHTML =
        '<header class="site-header">' +
        '<div class="bar">' +
        '<a class="brand" href="index.html"><span class="line">David A Gardner</span><span class="line">Apex Realty Group</span></a>' +
        '<button class="nav-toggle" data-nav-toggle aria-label="Toggle navigation" aria-expanded="false">☰</button>' +
        "<nav>" +
        navHtml +
        '<div class="theme-toggle" role="group" aria-label="Theme">' +
        '<button data-theme-set="light" type="button">Light</button>' +
        '<button data-theme-set="dark" type="button">Dark</button>' +
        "</div>" +
        "</nav>" +
        "</div>" +
        "</header>";

      var navToggle = this.querySelector("[data-nav-toggle]");
      var nav = this.querySelector("nav");
      navToggle.addEventListener("click", function () {
        var open = nav.classList.toggle("open");
        navToggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }
  }

  class SiteFooter extends HTMLElement {
    connectedCallback() {
      var year = new Date().getFullYear();
      this.innerHTML =
        '<footer class="site-footer">' +
        '<div class="wrap">' +
        "<div>" +
        "David A Gardner<br>" +
        "Apex Realty Group<br>" +
        "1305 Mifflin St, Huntingdon, PA 16652<br>" +
        'Cell: <a href="tel:8145997860">814-599-7860</a> &middot; ' +
        'Office: <a href="tel:8146412739">814-641-2739</a>' +
        "</div>" +
        '<div class="cols">' +
        "<nav>" +
        '<a href="index.html">Home</a>' +
        '<a href="listings.html">Listings</a>' +
        '<a href="about.html">About</a>' +
        '<a href="contact.html">Contact</a>' +
        "</nav>" +
        "</div>" +
        "</div>" +
        '<div class="wrap" style="padding-top:0;color:var(--text-faint);font-size:0.82rem;">' +
        "&copy; " +
        year +
        " David A Gardner. Listing data updated regularly from MLS." +
        "</div>" +
        "</footer>";
    }
  }

  customElements.define("site-header", SiteHeader);
  customElements.define("site-footer", SiteFooter);
})();
