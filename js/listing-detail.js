(function () {
  var LISTINGS_API_URL = "https://dagrealty-listings-api.aaron-d6f.workers.dev";

  function money(n) {
    if (n === null || n === undefined) return "Call for Price";
    return "$" + Math.round(n).toLocaleString();
  }

  function statusClass(status) {
    return (status || "").toLowerCase().replace(/\s+/g, "-");
  }

  function field(label, value) {
    if (value === null || value === undefined || value === "") return "";
    return '<div class="field"><div class="label">' + label + '</div><div class="value">' + value + "</div></div>";
  }

  function yesNo(v) {
    if (v === true) return "Yes";
    if (v === false) return "No";
    return null;
  }

  function renderFacts(l) {
    var facts = [
      ["Beds", l.bedrooms],
      ["Baths", l.total_baths],
      ["Sq Ft", l.total_sqft ? l.total_sqft.toLocaleString() : null],
      ["Acreage", l.acreage],
      ["Year Built", l.year_built],
    ];
    return facts
      .filter(function (f) { return f[1] !== null && f[1] !== undefined; })
      .map(function (f) {
        return '<div class="fact"><div class="value">' + f[1] + '</div><div class="label">' + f[0] + "</div></div>";
      })
      .join("");
  }

  function renderRooms(rooms) {
    if (!rooms || rooms.length === 0) return "";
    var rows = rooms
      .map(function (r) {
        return (
          "<tr><td>" + (r.room || "") + "</td><td>" + (r.level || "") + "</td><td>" +
          (r.size || "") + "</td><td>" + (r.description || "") + "</td></tr>"
        );
      })
      .join("");
    return (
      '<div class="detail-section"><h3>Rooms</h3><table class="room-table">' +
      "<thead><tr><th>Room</th><th>Level</th><th>Size</th><th>Description</th></tr></thead>" +
      "<tbody>" + rows + "</tbody></table></div>"
    );
  }

  function renderTags(items) {
    if (!items || items.length === 0) return "";
    return '<div class="tag-list">' + items.map(function (t) { return '<span class="tag">' + t + "</span>"; }).join("") + "</div>";
  }

  function render(l) {
    document.title = (l.address || "Listing") + ", " + (l.city || "") + " | David A Gardner Realty";

    var addr = [l.street_number, l.address].filter(Boolean).join(" ");
    document.getElementById("listing-price").textContent = money(l.list_price);
    document.getElementById("listing-address").textContent = addr + ", " + (l.city || "") + (l.state ? ", " + l.state : "") + " " + (l.zip || "");
    var statusEl = document.getElementById("listing-status");
    if (l.status) {
      statusEl.textContent = l.status;
      statusEl.className = "status-badge " + statusClass(l.status);
      statusEl.style.position = "static";
    } else {
      statusEl.remove();
    }

    document.getElementById("listing-facts").innerHTML = renderFacts(l);

    var overview = [
      field("Property Type", l.property_type),
      field("House Style", l.house_style),
      field("MLS Number", l.mls_number),
      field("County", l.county),
      field("Region", l.region),
      field("Zoning", l.zoning),
    ].join("");
    document.getElementById("section-overview").innerHTML = overview ? '<div class="field-list">' + overview + "</div>" : "";

    var interior = [
      field("Full Baths", l.full_baths),
      field("3/4 Baths", l.three_quarter_baths),
      field("Half Baths", l.half_baths),
      field("Basement", l.basement),
      field("Walkout Basement", yesNo(l.walkout_basement)),
      field("Fireplaces", l.fireplaces_count),
      field("Heating", l.heating_type),
      field("AC", l.ac_type),
      field("Included", l.included),
      field("Not Included", l.not_included),
    ].join("");
    document.getElementById("section-interior").innerHTML = interior ? '<div class="field-list">' + interior + "</div>" : "";

    var exterior = [
      field("Exterior", l.exterior),
      field("Roof", l.roof_type),
      field("Parking", l.parking),
      field("Garage Spaces", l.garage_spaces),
      field("Driveway", l.driveway),
      field("Water", l.water_type),
      field("Sewer", l.sewer_type),
      field("Flood Zone", l.flood_zone),
      field("Frontage (ft)", l.frontage_feet),
      field("Depth (ft)", l.depth_feet),
      field("Mobile Home OK", yesNo(l.mobile_home)),
    ].join("");
    document.getElementById("section-exterior").innerHTML = exterior ? '<div class="field-list">' + exterior + "</div>" : "";

    var schools = [
      field("Elementary School", l.elementary_school),
      field("Middle School", l.middle_school),
      field("High School", l.high_school),
    ].join("");
    document.getElementById("section-schools").innerHTML = schools ? '<div class="field-list">' + schools + "</div>" : "";

    var taxes = [
      field("Tax Year", l.tax_year),
      field("Total Taxes", l.total_taxes ? money(l.total_taxes) : null),
    ].join("");
    document.getElementById("section-taxes").innerHTML = taxes ? '<div class="field-list">' + taxes + "</div>" : "";

    document.getElementById("section-rooms").innerHTML = renderRooms(l.rooms);

    document.getElementById("section-description").innerHTML = l.public_comments
      ? "<p>" + l.public_comments + "</p>"
      : "<p>Contact David for full details on this property.</p>";

    var amenitiesHtml = renderTags((l.amenities || []).concat(l.property_features || []));
    document.getElementById("section-amenities").innerHTML = amenitiesHtml;
    document.getElementById("section-amenities-wrap").style.display = amenitiesHtml ? "" : "none";

    var tourLink = document.getElementById("virtual-tour-link");
    if (l.virtual_tour_url) {
      tourLink.href = l.virtual_tour_url;
      tourLink.style.display = "";
    } else {
      tourLink.style.display = "none";
    }

    window.DAGGallery.init(document.getElementById("gallery"), l.photos || []);
  }

  function init() {
    var params = new URLSearchParams(window.location.search);
    var mls = params.get("mls");
    var root = document.getElementById("listing-root");

    if (!mls) {
      root.innerHTML = '<div class="empty-state">No listing specified. <a href="listings.html">Browse all listings</a>.</div>';
      return;
    }

    fetch(LISTINGS_API_URL + "/listings/" + encodeURIComponent(mls))
      .then(function (res) {
        if (!res.ok) throw new Error("not found");
        return res.json();
      })
      .then(render)
      .catch(function () {
        root.innerHTML =
          '<div class="empty-state">This listing could not be found or is no longer available. <a href="listings.html">Browse all listings</a>.</div>';
      });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
