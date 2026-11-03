/* RoutePou web app: language, theme, install button, platform hints, connection check, offline cache.
   No inline script, no framework, no tracking. The only network calls are the two lookups in the connection check. */
(function () {
  "use strict";

  var DEFAULT_REPO = "Mahdi-mortazavi/RoutePou";
  var STORE = { lang: "routepou.lang", theme: "routepou.theme", before: "routepou.before" };
  var STR = window.ROUTEPOU_STRINGS || { fa: {}, en: {} };
  var root = document.documentElement;
  var $ = function (id) { return document.getElementById(id); };

  /* Browser storage can throw (private windows, blocked site data), so every access is guarded. */
  function load(key) { try { return window.localStorage.getItem(key); } catch (e) { return null; } }
  function save(key, value) { try { window.localStorage.setItem(key, value); } catch (e) { /* page still works without it */ } }
  function drop(key) { try { window.localStorage.removeItem(key); } catch (e) { /* ignore */ } }

  /* ---------- platform ---------- */
  function detectPlatform() {
    var ua = navigator.userAgent || "";
    var touchMac = /Macintosh/.test(ua) && navigator.maxTouchPoints > 1;
    if (/iPhone|iPad|iPod/.test(ua) || touchMac) { return "ios"; }
    if (/Android/.test(ua)) { return "android"; }
    if (/Windows/.test(ua)) { return "windows"; }
    return "other";
  }
  var platform = detectPlatform();
  root.setAttribute("data-platform", platform);

  /* ---------- links: point them at the repo this page is served from ---------- */
  function repoSlug() {
    var host = window.location.hostname;
    var m = /^([a-z0-9-]+)\.github\.io$/i.exec(host);
    var first = window.location.pathname.split("/").filter(Boolean)[0];
    if (m && first && !/\.[a-z0-9]+$/i.test(first)) { return m[1] + "/" + first; }
    return DEFAULT_REPO;
  }
  (function fixLinks() {
    var base = "https://github.com/" + repoSlug();
    var map = {
      win: base + "/releases/latest/download/RoutePou-windows-x64.exe",
      and: base + "/releases/latest/download/RoutePou-android.apk",
      repo: base,
      releases: base + "/releases",
      security: base + "/blob/main/SECURITY.md",
      license: base + "/blob/main/LICENSE"
    };
    var links = document.querySelectorAll("[data-link]");
    for (var i = 0; i < links.length; i++) {
      var target = map[links[i].getAttribute("data-link")];
      if (target) { links[i].setAttribute("href", target); }
    }
  })();

  /* ---------- language ---------- */
  var lang = load(STORE.lang) === "en" ? "en" : "fa";

  function t(key) {
    var table = STR[lang] || {};
    return table[key] !== undefined ? table[key] : (STR.fa[key] || key);
  }

  function applyLang() {
    root.setAttribute("lang", lang);
    root.setAttribute("dir", lang === "fa" ? "rtl" : "ltr");
    var nodes = document.querySelectorAll("[data-i18n]");
    for (var i = 0; i < nodes.length; i++) {
      var key = nodes[i].getAttribute("data-i18n");
      if (key === "check.idle") { continue; } /* the verdict line is driven by state, see setVerdict */
      nodes[i].textContent = t(key);
    }
    var aria = document.querySelectorAll("[data-i18n-aria]");
    for (var j = 0; j < aria.length; j++) {
      aria[j].setAttribute("aria-label", t(aria[j].getAttribute("data-i18n-aria")));
    }
    /* the language button names the other language, written in that language */
    $("langBtn").setAttribute("lang", lang === "fa" ? "en" : "fa");
    refreshInstallLabel();
    renderVerdict();
    renderReadings();
  }

  $("langBtn").addEventListener("click", function () {
    lang = lang === "fa" ? "en" : "fa";
    save(STORE.lang, lang);
    applyLang();
  });

  /* ---------- theme ---------- */
  var savedTheme = load(STORE.theme);
  if (savedTheme === "light" || savedTheme === "dark") { root.setAttribute("data-theme", savedTheme); }

  function currentTheme() {
    return root.getAttribute("data-theme") === "light" ? "light" : "dark"; /* dark is the default look */
  }
  $("themeBtn").addEventListener("click", function () {
    var next = currentTheme() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    save(STORE.theme, next);
  });

  /* ---------- install ---------- */
  var deferredPrompt = null;
  var installed = window.matchMedia && (window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true);
  var installButtons = [$("installBtn"), $("installHero")];
  var dialog = $("installDialog");

  function refreshInstallLabel() {
    for (var i = 0; i < installButtons.length; i++) {
      installButtons[i].textContent = t(installed ? "nav.installed" : "nav.install");
      installButtons[i].disabled = installed;
      if (installed) { installButtons[i].setAttribute("aria-disabled", "true"); }
    }
  }

  function openHelp() {
    if (dialog && typeof dialog.showModal === "function") {
      if (!dialog.open) { dialog.showModal(); }
    } else {
      window.alert(t("inst." + (platform === "ios" ? "ios" : platform === "android" ? "android" : "desktop")));
    }
  }

  function onInstallClick() {
    if (installed) { return; }
    if (deferredPrompt) {
      var promptEvent = deferredPrompt;
      deferredPrompt = null;
      promptEvent.prompt();
      promptEvent.userChoice.then(function (choice) {
        if (choice && choice.outcome === "accepted") { installed = true; refreshInstallLabel(); }
      }, function () { /* dismissed */ });
    } else {
      openHelp(); /* iOS and browsers without a install prompt: show how to add it by hand */
    }
  }
  for (var b = 0; b < installButtons.length; b++) { installButtons[b].addEventListener("click", onInstallClick); }

  window.addEventListener("beforeinstallprompt", function (event) {
    event.preventDefault();
    deferredPrompt = event;
  });
  window.addEventListener("appinstalled", function () { installed = true; deferredPrompt = null; refreshInstallLabel(); });

  $("instClose").addEventListener("click", function () { dialog.close(); });
  dialog.addEventListener("click", function (event) { if (event.target === dialog) { dialog.close(); } });

  /* ---------- connection check ---------- */
  var state = { now: null, before: null, status: "idle" }; /* status: idle | busy | changed | same | error | saved | done */

  (function restoreBefore() {
    var raw = load(STORE.before);
    if (!raw) { return; }
    try {
      var parsed = JSON.parse(raw);
      if (parsed && typeof parsed.ip === "string") { state.before = parsed; }
    } catch (e) { drop(STORE.before); }
  })();

  function setStatus(name) { state.status = name; renderVerdict(); }

  function renderVerdict() {
    var el = $("verdict");
    var key = { idle: "check.idle", busy: "check.busy", changed: "check.changed", same: "check.same",
                error: "check.error", saved: "check.saved", done: "check.done" }[state.status] || "check.idle";
    el.textContent = t(key);
    var visual = state.status === "saved" || state.status === "done" ? "idle" : state.status;
    el.setAttribute("data-state", visual);
  }

  function fillReading(prefix, data) {
    $(prefix + "Ip").textContent = data && data.ip ? data.ip : "-";
    $(prefix + "Where").textContent = data && data.where ? data.where : "";
  }

  function renderReadings() {
    fillReading("n", state.now);
    $("nLat").textContent = state.now && typeof state.now.ms === "number" ? t("check.latency") + ": " + state.now.ms + " ms" : "";
    fillReading("b", state.before);
    $("readBefore").hidden = !state.before;
    $("btnClear").hidden = !state.before;
    $("btnSave").disabled = !(state.now && state.now.ip);
  }

  function timedFetch(url, ms) {
    var ctrl = typeof AbortController === "function" ? new AbortController() : null;
    var timer = ctrl ? window.setTimeout(function () { ctrl.abort(); }, ms) : null;
    return window.fetch(url, { cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer", signal: ctrl ? ctrl.signal : undefined })
      .then(function (res) {
        if (timer) { window.clearTimeout(timer); }
        if (!res.ok) { throw new Error("http " + res.status); }
        return res.json();
      }, function (err) {
        if (timer) { window.clearTimeout(timer); }
        throw err;
      });
  }

  function describe(info) {
    if (!info || info.success === false) { return ""; }
    var place = [info.city, info.country].filter(Boolean).join(", ");
    var net = info.connection && (info.connection.isp || info.connection.org) ? (info.connection.isp || info.connection.org) : "";
    return [place, net].filter(Boolean).join(" / ");
  }

  function runCheck() {
    var button = $("btnCheck");
    button.disabled = true;
    setStatus("busy");
    var started = window.performance && performance.now ? performance.now() : Date.now();
    timedFetch("https://api.ipify.org?format=json", 8000).then(function (reply) {
      var ended = window.performance && performance.now ? performance.now() : Date.now();
      var ip = reply && typeof reply.ip === "string" ? reply.ip : "";
      if (!/^[0-9a-fA-F:.]{3,45}$/.test(ip)) { throw new Error("bad address"); }
      state.now = { ip: ip, where: "", ms: Math.round(ended - started) };
      renderReadings();
      /* location is a nicety: if this lookup fails the check still stands */
      return timedFetch("https://ipwho.is/" + encodeURIComponent(ip), 8000).then(function (info) {
        state.now.where = describe(info);
      }, function () { /* ignore */ });
    }).then(function () {
      renderReadings();
      if (state.before) { setStatus(state.before.ip !== state.now.ip ? "changed" : "same"); }
      else { setStatus("done"); }
    }, function () {
      state.now = null;
      renderReadings();
      setStatus("error");
    }).then(function () { button.disabled = false; });
  }

  $("btnCheck").addEventListener("click", runCheck);
  $("btnSave").addEventListener("click", function () {
    if (!state.now || !state.now.ip) { return; }
    state.before = { ip: state.now.ip, where: state.now.where || "" };
    save(STORE.before, JSON.stringify(state.before));
    renderReadings();
    setStatus("saved");
  });
  $("btnClear").addEventListener("click", function () {
    state.before = null;
    drop(STORE.before);
    renderReadings();
    setStatus("idle");
  });

  /* ---------- offline cache ---------- */
  if ("serviceWorker" in navigator && (window.location.protocol === "https:" || window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("sw.js").catch(function () { /* the site works without offline support */ });
    });
  }

  applyLang();
})();
