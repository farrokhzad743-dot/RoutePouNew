/* RoutePou download page: language, theme and the section layers. No tracking, no network calls. */
(function () {
  "use strict";
  var root = document.documentElement;
  var LANG_KEY = "routepou.site.lang", THEME_KEY = "routepou.site.theme";
  var TITLES = { fa: "RoutePou | دانلود برای ویندوز و اندروید", en: "RoutePou | Download for Windows and Android" };

  /* Browser storage can throw (private windows, blocked site data), so every access is guarded. */
  function save(key, value) { try { window.localStorage.setItem(key, value); } catch (e) { /* the page works without it */ } }
  function saved(key) { try { return window.localStorage.getItem(key); } catch (e) { return null; } }

  /* ---------- language ---------- */
  function setLang(lang) {
    root.setAttribute("lang", lang);
    root.setAttribute("dir", lang === "fa" ? "rtl" : "ltr");
    document.title = TITLES[lang];
  }
  setLang(root.getAttribute("lang") === "en" ? "en" : "fa");
  var langButton = document.getElementById("langBtn");
  if (langButton) {
    langButton.addEventListener("click", function () {
      var next = root.getAttribute("lang") === "fa" ? "en" : "fa";
      setLang(next);
      save(LANG_KEY, next);
    });
  }

  /* ---------- theme, and the app pictures that follow it ---------- */
  var picturesLoaded = false;
  var meta = document.querySelector('meta[name="theme-color"]');
  function applyPictures() {
    var dark = root.getAttribute("data-theme") === "dark";
    var images = document.querySelectorAll("img[data-shot]");
    for (var i = 0; i < images.length; i++) {
      var wanted = images[i].getAttribute("data-shot") + (dark ? "-dark" : "") + ".webp";
      if (images[i].getAttribute("src") !== wanted) { images[i].setAttribute("src", wanted); }
    }
    picturesLoaded = true;
  }
  function setTheme(theme) {
    root.setAttribute("data-theme", theme);
    if (meta) { meta.setAttribute("content", theme === "dark" ? "#0f0f11" : "#ffffff"); }
    applyPictures();
  }
  setTheme(root.getAttribute("data-theme") === "dark" ? "dark" : "light");
  var themeButton = document.getElementById("themeBtn");
  if (themeButton) {
    themeButton.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      setTheme(next);
      save(THEME_KEY, next);
    });
  }
  /* Without a saved choice, follow the system when it changes. */
  if (window.matchMedia && !saved(THEME_KEY)) {
    var query = window.matchMedia("(prefers-color-scheme: dark)");
    var follow = function (event) { if (!saved(THEME_KEY)) { setTheme(event.matches ? "dark" : "light"); } };
    if (query.addEventListener) { query.addEventListener("change", follow); }
  }

  /* ---------- layers (one <dialog> per section) ---------- */
  function layerOf(id) { var el = document.getElementById(id); return el && el.tagName === "DIALOG" ? el : null; }
  function openLayer(id) {
    var layer = layerOf(id);
    if (!layer || layer.open) { return; }
    if (typeof layer.showModal === "function") { layer.showModal(); } else { layer.setAttribute("open", ""); }
    root.classList.add("lock");
    /* the cover picture of the video is fetched only now, so the first view stays small */
    var teaser = layer.querySelector("video[data-poster]");
    if (teaser && !teaser.getAttribute("poster")) { teaser.setAttribute("poster", teaser.getAttribute("data-poster")); }
    try { history.replaceState(null, "", "#" + id); } catch (e) { /* not important */ }
  }
  function closed() {
    if (!document.querySelector("dialog[open]")) { root.classList.remove("lock"); }
    try { if (location.hash) { history.replaceState(null, "", location.pathname + location.search); } } catch (e) { /* not important */ }
  }
  var openers = document.querySelectorAll("[data-open]");
  for (var i = 0; i < openers.length; i++) {
    openers[i].addEventListener("click", function (event) { openLayer(event.currentTarget.getAttribute("data-open")); });
  }
  var layers = document.querySelectorAll("dialog.layer");
  for (var j = 0; j < layers.length; j++) {
    layers[j].addEventListener("close", function (event) {
      var playing = event.currentTarget.querySelector("video");
      if (playing) { playing.pause(); }
      closed();
    });
    /* a click on the dimmed area (the dialog element itself, outside its content) closes the layer */
    layers[j].addEventListener("click", function (event) {
      if (event.target === event.currentTarget) { event.currentTarget.close(); }
    });
  }
  var closers = document.querySelectorAll("[data-close]");
  for (var k = 0; k < closers.length; k++) {
    closers[k].addEventListener("click", function (event) {
      var layer = event.currentTarget.closest("dialog");
      if (layer) { layer.close(); }
    });
  }
  if (location.hash.length > 1) { openLayer(decodeURIComponent(location.hash.slice(1))); }
  if (!picturesLoaded) { applyPictures(); }
})();
