/* Landing demo: the fictional specimen card -> HR record, animated.
   Values are the real /hr/passport response for app/web/static/demo (specimen seed 7). */
(function () {
  const { t } = window.Site;
  const FIELDS = ["surname", "name", "patronymic", "gender", "date_of_birth", "national_id", "passport_id", "marital_status"];
  const DATA = {
    tg: { surname: "Маҳмудова", name: "Гулнора", patronymic: "Абдуқодирзода", gender: "Зан", date_of_birth: "1991-02-22",
      national_id: "3518609139099", passport_id: "A60308246", marital_status: "Оиладор" },
    en: { surname: "Mahmudova", name: "Gulnora", patronymic: "Abduqodirzoda", gender: "Female", date_of_birth: "1991-02-22",
      national_id: "3518609139099", passport_id: "A60308246", marital_status: "Married" },
  };
  const SCORES = { surname: 0.96, name: 0.95, patronymic: 0.95, marital_status: 0.95 };
  const ELAPSED = "3.4 s";
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  let run = 0; // bumps on every (re)start so a stale animation stops

  const sleep = (ms) => new Promise((r) => setTimeout(r, reduced ? 0 : ms));

  function rows() {
    const box = document.getElementById("demo-rows");
    box.innerHTML = FIELDS.map((f) => `<div class="drow" data-f="${f}">
        <span class="l">${t("f." + f)}</span><span class="v"></span>
        <span class="s${f in SCORES ? "" : " none"}"><b></b></span></div>`).join("");
  }

  function status(state) {
    const chip = document.getElementById("demo-status");
    chip.className = "chip" + (state === "done" ? " ok" : "");
    chip.querySelector("span").textContent = state === "done"
      ? `200 · ${t("demo.done")} · ${ELAPSED} · needs_review: 0` : "POST /hr/passport";
  }

  async function play() {
    const me = ++run;
    const stage = document.getElementById("demo-stage");
    const values = DATA[window.Site.lang === "en" ? "en" : "tg"];
    rows();
    status("run");
    stage.classList.add("running");
    await sleep(1600);
    for (const f of FIELDS) {
      if (me !== run) return;
      const row = stage.querySelector(`.drow[data-f="${f}"]`);
      const v = row.querySelector(".v");
      v.classList.add("typing");
      const text = values[f];
      for (let i = 1; i <= text.length; i++) {
        if (me !== run) return;
        v.textContent = text.slice(0, i);
        await sleep(22);
      }
      v.classList.remove("typing");
      if (f in SCORES) row.querySelector(".s b").style.width = Math.round(SCORES[f] * 100) + "%";
      else row.querySelector(".s").textContent = "✓ MRZ"; // dates and numbers: confirmed by MRZ check digits
      row.classList.add("flash");
      setTimeout(() => row.classList.remove("flash"), 500);
      await sleep(90);
    }
    stage.classList.remove("running");
    status("done");
  }

  document.addEventListener("DOMContentLoaded", () => {
    const stage = document.getElementById("demo-stage");
    if (!stage) return;
    rows();
    let started = false;
    const io = new IntersectionObserver((entries) => {
      if (!started && entries.some((e) => e.isIntersecting)) { started = true; play(); io.disconnect(); }
    }, { threshold: 0.35 });
    io.observe(stage);
    document.getElementById("demo-replay").addEventListener("click", play);
    window.Site.onLang(() => (started ? play() : rows()));
  });
})();
