(function () {
  var LISTINGS_API_URL = "https://dagrealty-listings-api.aaron-d6f.workers.dev";
  var MAX_FEATURED = 6;
  var GALLERY_INTERVAL_MS = 6000;

  function primaryPhotoUrl(listing) {
    var photos = listing.photos || [];
    var primary = photos.find(function (p) { return p.is_primary; }) || photos[0];
    return primary ? (primary.full_url || primary.thumb_url) : null;
  }

  function shuffle(arr) {
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = arr[i];
      arr[i] = arr[j];
      arr[j] = tmp;
    }
    return arr;
  }

  function renderFeaturedGrid(active) {
    var grid = document.getElementById("featured-grid");
    if (!grid) return;

    var featured = active.filter(function (l) { return l.featured; });
    var chosen = (featured.length ? featured : active)
      .slice()
      .sort(function (a, b) { return new Date(b.updated_at) - new Date(a.updated_at); })
      .slice(0, MAX_FEATURED);

    if (chosen.length === 0) {
      grid.innerHTML = '<div class="empty-state">No active listings right now — <a href="contact.html">get in touch</a> to hear about what\'s coming.</div>';
      return;
    }
    grid.innerHTML = chosen.map(window.DAGListingCard.html).join("");
  }

  function initHeroGallery(active) {
    var container = document.getElementById("hero-gallery");
    if (!container) return;

    var urls = shuffle(active.map(primaryPhotoUrl).filter(Boolean));
    if (urls.length === 0) return;

    var hero = container.closest(".hero");
    urls.forEach(function (url, i) {
      var img = document.createElement("img");
      img.src = url;
      img.alt = "";
      img.loading = i === 0 ? "eager" : "lazy";
      if (i === 0) img.className = "is-active";
      container.appendChild(img);
    });
    if (hero) hero.classList.add("has-gallery");

    if (urls.length > 1) {
      var current = 0;
      setInterval(function () {
        var imgs = container.querySelectorAll("img");
        imgs[current].classList.remove("is-active");
        current = (current + 1) % imgs.length;
        imgs[current].classList.add("is-active");
      }, GALLERY_INTERVAL_MS);
    }
  }

  function init() {
    var grid = document.getElementById("featured-grid");
    if (grid) grid.innerHTML = '<div class="empty-state">Loading listings…</div>';

    fetch(LISTINGS_API_URL + "/listings")
      .then(function (res) {
        if (!res.ok) throw new Error("bad response " + res.status);
        return res.json();
      })
      .then(function (data) {
        var listings = data.listings || [];
        var active = listings.filter(function (l) { return l.status === "Active"; });

        renderFeaturedGrid(active);
        initHeroGallery(active);
      })
      .catch(function (err) {
        console.error(err);
        if (grid) grid.innerHTML = '<div class="empty-state">Listings are temporarily unavailable. Please check back shortly.</div>';
      });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
