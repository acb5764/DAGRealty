(function () {
  var PLACEHOLDER_IMG =
    'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="100%" height="100%" fill="%231a1f28"/><text x="50%" y="50%" fill="%236b7688" font-family="sans-serif" font-size="16" text-anchor="middle" dy=".3em">No Photo</text></svg>';

  function money(n) {
    if (n === null || n === undefined) return "Call for Price";
    return "$" + Math.round(n).toLocaleString();
  }

  function statusClass(status) {
    return (status || "").toLowerCase().replace(/\s+/g, "-");
  }

  function primaryPhoto(listing) {
    var photos = listing.photos || [];
    var primary = photos.find(function (p) {
      return p.is_primary;
    });
    return (primary || photos[0] || {}).thumb_url || PLACEHOLDER_IMG;
  }

  function addressLine(listing) {
    var parts = [listing.street_number, listing.address].filter(Boolean);
    return parts.join(" ") || "Address unavailable";
  }

  function html(listing) {
    var facts = [];
    if (listing.bedrooms) facts.push("<span><strong>" + listing.bedrooms + "</strong> bd</span>");
    if (listing.total_baths) facts.push("<span><strong>" + listing.total_baths + "</strong> ba</span>");
    if (listing.total_sqft) facts.push("<span><strong>" + listing.total_sqft.toLocaleString() + "</strong> sqft</span>");
    if (listing.acreage) facts.push("<span><strong>" + listing.acreage + "</strong> ac</span>");

    return (
      '<div class="listing-card">' +
      '<a class="card-link" href="listing.html?mls=' + encodeURIComponent(listing.mls_number) + '">' +
      '<div class="thumb">' +
      '<img src="' + primaryPhoto(listing) + '" alt="' + addressLine(listing) + '" loading="lazy" onerror="this.src=\'' + PLACEHOLDER_IMG + '\'">' +
      (listing.status ? '<span class="status-badge ' + statusClass(listing.status) + '">' + listing.status + "</span>" : "") +
      "</div>" +
      '<div class="body">' +
      '<div class="price">' + money(listing.list_price) + "</div>" +
      '<div class="addr">' + addressLine(listing) + ", " + (listing.city || "") + "</div>" +
      '<div class="facts">' + facts.join("") + "</div>" +
      "</div>" +
      "</a>" +
      "</div>"
    );
  }

  window.DAGListingCard = { html: html, money: money, addressLine: addressLine };
})();
