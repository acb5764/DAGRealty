(function () {
  var LISTINGS_API_URL = "REPLACE_WITH_WORKER_URL"; // TODO: set after `wrangler deploy` (see worker/README.md)

  var allListings = [];

  function populateCityOptions(listings) {
    var citySelect = document.getElementById("filter-city");
    var cities = Array.from(new Set(listings.map(function (l) { return l.city; }).filter(Boolean))).sort();
    cities.forEach(function (city) {
      var opt = document.createElement("option");
      opt.value = city;
      opt.textContent = city;
      citySelect.appendChild(opt);
    });
  }

  function applyFiltersAndSort() {
    var propertyType = document.getElementById("filter-type").value;
    var city = document.getElementById("filter-city").value;
    var minPrice = parseFloat(document.getElementById("filter-min-price").value);
    var maxPrice = parseFloat(document.getElementById("filter-max-price").value);
    var minBeds = parseFloat(document.getElementById("filter-min-beds").value);
    var sortBy = document.getElementById("filter-sort").value;

    var filtered = allListings.filter(function (l) {
      if (propertyType && l.property_type !== propertyType) return false;
      if (city && l.city !== city) return false;
      if (!isNaN(minPrice) && (l.list_price || 0) < minPrice) return false;
      if (!isNaN(maxPrice) && (l.list_price || Infinity) > maxPrice) return false;
      if (!isNaN(minBeds) && (l.bedrooms || 0) < minBeds) return false;
      return true;
    });

    var sorters = {
      price_asc: function (a, b) { return (a.list_price || 0) - (b.list_price || 0); },
      price_desc: function (a, b) { return (b.list_price || 0) - (a.list_price || 0); },
      sqft_desc: function (a, b) { return (b.total_sqft || 0) - (a.total_sqft || 0); },
      acreage_desc: function (a, b) { return (b.acreage || 0) - (a.acreage || 0); },
      year_desc: function (a, b) { return (b.year_built || 0) - (a.year_built || 0); },
      newest: function (a, b) { return new Date(b.updated_at) - new Date(a.updated_at); },
    };
    filtered.sort(sorters[sortBy] || sorters.price_asc);

    renderGrid(filtered);
  }

  function renderGrid(listings) {
    var grid = document.getElementById("listing-grid");
    var count = document.getElementById("results-count");
    count.textContent = listings.length + (listings.length === 1 ? " listing" : " listings") + " found";

    if (listings.length === 0) {
      grid.innerHTML = '<div class="empty-state">No listings match those filters. Try widening your search.</div>';
      return;
    }
    grid.innerHTML = listings.map(window.DAGListingCard.html).join("");
  }

  function init() {
    var grid = document.getElementById("listing-grid");
    grid.innerHTML = '<div class="empty-state">Loading listings…</div>';

    fetch(LISTINGS_API_URL + "/listings")
      .then(function (res) {
        if (!res.ok) throw new Error("bad response " + res.status);
        return res.json();
      })
      .then(function (data) {
        allListings = data.listings || [];
        populateCityOptions(allListings);
        applyFiltersAndSort();
        ["filter-type", "filter-city", "filter-min-price", "filter-max-price", "filter-min-beds", "filter-sort"].forEach(
          function (id) {
            document.getElementById(id).addEventListener("input", applyFiltersAndSort);
            document.getElementById(id).addEventListener("change", applyFiltersAndSort);
          }
        );
        document.getElementById("filter-reset").addEventListener("click", function () {
          document.querySelectorAll(".filter-bar select, .filter-bar input").forEach(function (el) {
            el.value = "";
          });
          applyFiltersAndSort();
        });
      })
      .catch(function (err) {
        console.error(err);
        grid.innerHTML =
          '<div class="empty-state">Listings are temporarily unavailable. Please check back shortly, or <a href="contact.html">contact David directly</a>.</div>';
      });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
