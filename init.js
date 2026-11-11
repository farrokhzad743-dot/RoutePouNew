/* Runs first, before anything is drawn, so the saved theme and language show without a flash. */
(function () {
  var d = document.documentElement, theme = null, lang = null;
  try { theme = localStorage.getItem("routepou.site.theme"); lang = localStorage.getItem("routepou.site.lang"); } catch (e) { /* storage can be blocked */ }
  if (theme !== "dark" && theme !== "light") {
    theme = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  d.setAttribute("data-theme", theme);
  if (lang === "en") { d.setAttribute("lang", "en"); d.setAttribute("dir", "ltr"); }
  d.className += " js";
})();
