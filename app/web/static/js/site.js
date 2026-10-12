/* Shared: language detection, applying translations, the language switcher, nav state. */
(function () {
  const LANGS = window.I18N_LANGS;
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
    del(k) { try { localStorage.removeItem(k); } catch { /* ignore */ } },
  };

  function detect() {
    const q = new URLSearchParams(location.search).get("lang");
    if (q && LANGS.includes(q)) return q;
    const saved = store.get("tocr.lang");
    if (saved && LANGS.includes(saved)) return saved;
    for (const l of navigator.languages || [navigator.language || ""]) {
      const base = l.slice(0, 2).toLowerCase();
      if (LANGS.includes(base)) return base;
    }
    return "ru";
  }

  let lang = detect();
  const listeners = [];

  function t(key) {
    const row = window.I18N[key];
    if (!row) { console.warn("i18n: missing key", key); return key; }
    return row[LANGS.indexOf(lang)];
  }

  function apply(root = document) {
    document.documentElement.lang = lang;
    root.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    root.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
    root.querySelectorAll("[data-i18n-title]").forEach((el) => { el.title = t(el.dataset.i18nTitle); });
    const titleKey = document.body.dataset.titleKey;
    if (titleKey) document.title = t(titleKey);
    document.querySelectorAll(".lang-select").forEach((s) => { s.value = lang; });
    // keep ?lang= on internal links so a shared link opens in the same language
    document.querySelectorAll("a[data-keep-lang]").forEach((a) => {
      const u = new URL(a.getAttribute("href"), location.href);
      u.searchParams.set("lang", lang);
      a.href = u.pathname + u.search + u.hash;
    });
  }

  function setLang(next) {
    if (!LANGS.includes(next) || next === lang) return;
    lang = next;
    store.set("tocr.lang", lang);
    const u = new URL(location.href);
    u.searchParams.set("lang", lang);
    history.replaceState(null, "", u);
    apply();
    listeners.forEach((fn) => fn(lang));
  }

  function buildSwitchers() {
    document.querySelectorAll(".lang-select").forEach((sel) => {
      sel.innerHTML = LANGS.map((l) => `<option value="${l}">${window.I18N_NAMES[l]}</option>`).join("");
      sel.addEventListener("change", () => setLang(sel.value));
    });
  }

  window.Site = { t, apply, setLang, store, get lang() { return lang; }, onLang: (fn) => listeners.push(fn) };

  document.addEventListener("DOMContentLoaded", () => {
    buildSwitchers();
    apply();
    const nav = document.querySelector(".nav");
    if (nav) {
      const onScroll = () => nav.classList.toggle("scrolled", scrollY > 40);
      addEventListener("scroll", onScroll, { passive: true });
      onScroll();
    }
    document.querySelectorAll("[data-year]").forEach((el) => { el.textContent = new Date().getFullYear(); });
  });
})();
