(function () {
  function init(container, photos) {
    if (!photos || photos.length === 0) {
      container.innerHTML = "";
      return;
    }

    var index = 0;

    container.innerHTML =
      '<div class="main-photo">' +
      '<img id="gallery-main-img" src="" alt="Listing photo">' +
      '<button class="nav-arrow prev" type="button" aria-label="Previous photo">&#8249;</button>' +
      '<button class="nav-arrow next" type="button" aria-label="Next photo">&#8250;</button>' +
      '<span class="counter" id="gallery-counter"></span>' +
      "</div>" +
      '<div class="thumb-strip" id="gallery-thumbs"></div>' +
      '<div class="lightbox" id="gallery-lightbox">' +
      '<button class="close" type="button" aria-label="Close">&times;</button>' +
      '<img id="gallery-lightbox-img" src="" alt="Listing photo, enlarged">' +
      "</div>";

    var mainImg = container.querySelector("#gallery-main-img");
    var counter = container.querySelector("#gallery-counter");
    var thumbStrip = container.querySelector("#gallery-thumbs");
    var lightbox = container.querySelector("#gallery-lightbox");
    var lightboxImg = container.querySelector("#gallery-lightbox-img");

    thumbStrip.innerHTML = photos
      .map(function (p, i) {
        return '<img data-index="' + i + '" src="' + p.thumb_url + '" alt="Photo ' + (i + 1) + '">';
      })
      .join("");

    function render() {
      var photo = photos[index];
      mainImg.src = photo.full_url;
      counter.textContent = (index + 1) + " / " + photos.length;
      thumbStrip.querySelectorAll("img").forEach(function (img, i) {
        img.classList.toggle("active", i === index);
      });
      var active = thumbStrip.querySelector("img.active");
      if (active) active.scrollIntoView({ inline: "center", block: "nearest" });
    }

    function go(delta) {
      index = (index + delta + photos.length) % photos.length;
      render();
    }

    container.querySelector(".nav-arrow.prev").addEventListener("click", function () { go(-1); });
    container.querySelector(".nav-arrow.next").addEventListener("click", function () { go(1); });
    thumbStrip.addEventListener("click", function (e) {
      var img = e.target.closest("img");
      if (!img) return;
      index = parseInt(img.dataset.index, 10);
      render();
    });

    mainImg.addEventListener("click", function () {
      lightboxImg.src = photos[index].full_url;
      lightbox.classList.add("open");
    });
    lightbox.addEventListener("click", function (e) {
      if (e.target === lightbox || e.target.classList.contains("close")) {
        lightbox.classList.remove("open");
      }
    });
    document.addEventListener("keydown", function (e) {
      if (lightbox.classList.contains("open")) {
        if (e.key === "Escape") lightbox.classList.remove("open");
        if (e.key === "ArrowLeft") { go(-1); lightboxImg.src = photos[index].full_url; }
        if (e.key === "ArrowRight") { go(1); lightboxImg.src = photos[index].full_url; }
      } else if (document.activeElement === document.body || container.contains(document.activeElement)) {
        if (e.key === "ArrowLeft") go(-1);
        if (e.key === "ArrowRight") go(1);
      }
    });

    render();
  }

  window.DAGGallery = { init: init };
})();
