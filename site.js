/* RoutePou download page: language switch and a gentle reveal. No tracking, no network calls. */
(function () {
  "use strict";
  var root = document.documentElement;
  root.classList.add("js");

  var KEY = "routepou.site.lang";
  var TITLES = { fa: "RoutePou | دانلود برای ویندوز و اندروید", en: "RoutePou | Download for Windows and Android" };

  /* Browser storage can throw (private windows, blocked site data), so every access is guarded. */
  function load() { try { return window.localStorage.getItem(KEY); } catch (e) { return null; } }
  function save(value) { try { window.localStorage.setItem(KEY, value); } catch (e) { /* the page works without it */ } }

  function setLang(lang) {
    root.setAttribute("lang", lang);
    root.setAttribute("dir", lang === "fa" ? "rtl" : "ltr");
    document.title = TITLES[lang];
  }

  var saved = load();
  setLang(saved === "en" ? "en" : "fa"); /* Persian is the default */

  var button = document.getElementById("langBtn");
  if (button) {
    button.addEventListener("click", function () {
      var next = root.getAttribute("lang") === "fa" ? "en" : "fa";
      setLang(next);
      save(next);
    });
  }

  /* Reveal blocks as they scroll into view. Without IntersectionObserver everything simply shows. */
  var blocks = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window)) {
    for (var i = 0; i < blocks.length; i++) { blocks[i].classList.add("in"); }
    return;
  }
  var observer = new IntersectionObserver(function (entries) {
    for (var j = 0; j < entries.length; j++) {
      if (entries[j].isIntersecting) {
        entries[j].target.classList.add("in");
        observer.unobserve(entries[j].target);
      }
    }
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
  for (var k = 0; k < blocks.length; k++) { observer.observe(blocks[k]); }
})();
