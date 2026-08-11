(function () {
  var LISTINGS_API_URL = "https://dagrealty-listings-api.aaron-d6f.workers.dev";
  var MAX_FEATURED = 6;

  function init() {
    var grid = document.getElementById("featured-grid");
    if (!grid) return;
    grid.innerHTML = '<div class="empty-state">Loading listings…</div>';

    fetch(LISTINGS_API_URL + "/listings")
      .then(function (res) {
        if (!res.ok) throw new Error("bad response " + res.status);
        return res.json();
      })
      .then(function (data) {
        var listings = data.listings || [];
        var active = listings.filter(function (l) { return l.status === "Active"; });
        var featured = active.filter(function (l) { return l.featured; });
        var chosen = (featured.length ? featured : active)
          .sort(function (a, b) { return new Date(b.updated_at) - new Date(a.updated_at); })
          .slice(0, MAX_FEATURED);

        if (chosen.length === 0) {
          grid.innerHTML = '<div class="empty-state">No active listings right now — <a href="contact.html">get in touch</a> to hear about what\'s coming.</div>';
          return;
        }
        grid.innerHTML = chosen.map(window.DAGListingCard.html).join("");
      })
      .catch(function (err) {
        console.error(err);
        grid.innerHTML = '<div class="empty-state">Listings are temporarily unavailable. Please check back shortly.</div>';
      });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
