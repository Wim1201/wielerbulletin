/* Wielerbulletin — player logic.
 * Reads feed.json (written by scripts/build_episodes.py), plays the newest
 * episode, draws the waveform as the seam between the yellow and black halves,
 * and keeps lock-screen controls in sync through the Media Session API. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const app = $("app");
  const audio = $("audio");
  const canvas = $("wave");
  const ctx = canvas.getContext("2d");
  const scrub = $("scrub");
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // canvas colours follow the CSS theme (team yellow, or club gold in the special)
  const COLORS = { yellow: "#FFDD00", honey: "#D9B500", black: "#000000", chalk: "#F4F2E6" };
  function syncThemeColors() {
    const cs = getComputedStyle(app);
    COLORS.yellow = cs.getPropertyValue("--yellow").trim() || COLORS.yellow;
    const honey = cs.getPropertyValue("--honey").trim();
    // the CSS honey is a touch light for the unplayed wave; darken the daily one slightly
    COLORS.honey = app.dataset.kind === "special" ? honey : "#D9B500";
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", COLORS.yellow);
  }
  const RATES = [1, 1.25, 1.5];

  let episodes = [];
  let current = null;
  let rafId = 0;
  let amp = 0;

  /* ---------- small storage helpers (storage can be unavailable) ---------- */
  const store = {
    get(key, fallback) {
      try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
    },
    set(key, value) {
      try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* ignore */ }
    },
  };
  const positions = store.get("wb.positions", {});
  const heard = new Set(store.get("wb.heard", []));

  /* ---------- episode helpers ---------- */
  // id is unique per episode (a Friday has the bulletin plus the special); older feeds only had date
  const keyOf = (ep) => ep.id || ep.date;
  const isDaily = (ep) => (ep.kind || "dagelijks") === "dagelijks";
  const mainEpisode = (list) => list.find(isDaily) || list[0];

  /* ---------- formatting ---------- */
  const fmtTime = (s) => {
    s = Math.max(0, Math.floor(s || 0));
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  };
  const fmtDay = (iso, withWeekday = true) => {
    const d = new Date(`${iso}T12:00:00`);
    return d.toLocaleDateString("nl-NL", withWeekday
      ? { weekday: "long", day: "numeric", month: "long" }
      : { day: "numeric", month: "long" });
  };
  const todayIso = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  };

  /* ---------- waveform seam ---------- */
  function sizeCanvas() {
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    const rect = canvas.getBoundingClientRect();
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw();
  }

  function idlePeaks(n = 120) {
    return Array.from({ length: n }, (_, i) =>
      0.35 + 0.25 * Math.sin(i / 5) * Math.sin(i / 13));
  }

  function draw() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    const peaks = current?.peaks?.length ? current.peaks : idlePeaks();
    const n = peaks.length;
    const dur = current?.duration || 1;
    const progress = current ? Math.min(1, audio.currentTime / dur) : 0;
    const playX = progress * w;
    const base = h * 0.16, depth = h * 0.62;
    const playing = !audio.paused;
    const t = performance.now() / 1000;

    // y position of the seam at sample i, with a live swell around the playhead
    const yAt = (i) => {
      const x = (i / (n - 1)) * w;
      let v = peaks[i];
      if (playing && !reduceMotion) {
        const d = (x - playX) / (w * 0.05);
        v *= 1 + amp * 0.45 * Math.exp(-d * d) * (0.8 + 0.2 * Math.sin(t * 9 + i));
      }
      return base + Math.min(1.15, v) * depth;
    };

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = COLORS.black;
    ctx.fillRect(0, 0, w, h);

    // one smooth path for the yellow region, then clip into played/unplayed
    const path = new Path2D();
    path.moveTo(0, 0);
    path.lineTo(0, yAt(0));
    for (let i = 1; i < n; i++) {
      const x0 = ((i - 1) / (n - 1)) * w, x1 = (i / (n - 1)) * w;
      const y0 = yAt(i - 1), y1 = yAt(i);
      path.quadraticCurveTo(x0, y0, (x0 + x1) / 2, (y0 + y1) / 2);
    }
    path.lineTo(w, yAt(n - 1));
    path.lineTo(w, 0);
    path.closePath();

    ctx.save();
    ctx.beginPath(); ctx.rect(0, 0, playX, h); ctx.clip();
    ctx.fillStyle = COLORS.yellow; ctx.fill(path);
    ctx.restore();

    ctx.save();
    ctx.beginPath(); ctx.rect(playX, 0, w - playX, h); ctx.clip();
    ctx.fillStyle = COLORS.honey; ctx.fill(path);
    ctx.restore();

    // chapter ticks along the bottom edge
    if (current?.chapters) {
      ctx.fillStyle = "#3A3A32";
      for (const ch of current.chapters.slice(1)) {
        const x = (ch.start / dur) * w;
        const tick = ch.level === 3 ? 5 : 10;   // sub-chapters get a shorter tick
        ctx.fillRect(Math.round(x), h - tick, 2, tick);
      }
    }

    // playhead: a yellow marker riding just under the seam
    if (current) {
      const i = Math.round(progress * (n - 1));
      const y = Math.min(h - 8, yAt(i) + 12);
      ctx.fillStyle = COLORS.yellow;
      ctx.beginPath(); ctx.arc(Math.max(6, Math.min(w - 6, playX)), y, 6, 0, Math.PI * 2); ctx.fill();
    }
  }

  /* ---------- live loudness for ring + swell ---------- */
  function loudness() {
    if (!current?.peaks?.length || !current.duration) return 0;
    const p = current.peaks;
    const f = (audio.currentTime / current.duration) * (p.length - 1);
    const i = Math.floor(f), k = f - i;
    const v = (p[i] ?? 0) * (1 - k) + (p[i + 1] ?? p[i] ?? 0) * k;
    const t = audio.currentTime;
    // syllable-like flutter on top of the slow envelope
    const flutter = 0.55 + 0.45 * Math.abs(Math.sin(t * 7.3) * Math.sin(t * 3.1 + 1));
    return Math.max(0, Math.min(1, v * flutter));
  }

  function loop() {
    const target = audio.paused ? 0 : loudness();
    amp += (target - amp) * 0.25;
    document.documentElement.style.setProperty("--amp", amp.toFixed(3));
    updateProgress();
    draw();
    if (!audio.paused || amp > 0.01) rafId = requestAnimationFrame(loop);
    else rafId = 0;
  }
  const kick = () => { if (!rafId) rafId = requestAnimationFrame(loop); };

  /* ---------- rendering the page ---------- */
  function renderEpisode() {
    const ep = current;
    const isToday = ep.date === todayIso();
    $("dateline").textContent = ep.label
      ? `${ep.label}, ${fmtDay(ep.date, false)}`
      : isToday ? `Vandaag, ${fmtDay(ep.date, false)}` : fmtDay(ep.date);
    app.dataset.kind = isDaily(ep) ? "dagelijks" : "special";
    syncThemeColors();
    $("dateline").setAttribute("datetime", ep.date);
    $("headline").textContent = ep.title;
    $("summary").textContent = ep.summary || "";
    $("total").textContent = `van ${fmtTime(ep.duration)}`;

    const list = $("chapters");
    list.replaceChildren(...ep.chapters.map((ch, idx) => {
      const li = document.createElement("li");
      const b = document.createElement("button");
      b.type = "button";
      b.innerHTML = `<span class="at">${fmtTime(ch.start)}</span><span class="name"></span><span class="bar"></span>`;
      b.querySelector(".name").textContent = ch.title;
      b.addEventListener("click", () => { seek(ch.start); if (audio.paused) play(); });
      li.dataset.idx = idx;
      if (ch.level === 3) li.classList.add("sub");
      if (/jonge renner/i.test(ch.title)) li.classList.add("club");
      li.append(b);
      return li;
    }));
    renderArchive();
    updateProgress();
    draw();
  }

  function renderArchive() {
    const list = $("archive");
    list.replaceChildren(...episodes.filter((e) => e !== current).map((ep) => {
      const li = document.createElement("li");
      if (heard.has(keyOf(ep))) li.className = "heard";
      const b = document.createElement("button");
      b.type = "button";
      b.innerHTML = `<span class="day"></span><span class="t"></span><span class="len"></span>`;
      const day = b.querySelector(".day");
      if (ep.label) {
        const tag = document.createElement("span");
        tag.className = "tag";
        tag.textContent = ep.label;
        day.append(tag, " ");
      }
      day.append(fmtDay(ep.date));
      b.querySelector(".t").textContent = ep.title;
      b.querySelector(".len").textContent = fmtTime(ep.duration);
      b.addEventListener("click", () => {
        load(ep, true);
        window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
      });
      li.append(b);
      return li;
    }));
  }

  function chapterIndexAt(t) {
    const chs = current?.chapters || [];
    let idx = 0;
    chs.forEach((c, i) => { if (t >= c.start) idx = i; });
    return idx;
  }

  function updateProgress() {
    if (!current) return;
    const t = audio.currentTime;
    $("now").textContent = fmtTime(t);
    scrub.value = Math.round((t / (current.duration || 1)) * 1000);
    scrub.setAttribute("aria-valuetext", `${fmtTime(t)} van ${fmtTime(current.duration)}`);
    const idx = chapterIndexAt(t);
    const chs = current.chapters;
    document.querySelectorAll("#chapters li").forEach((li, i) => {
      li.classList.toggle("current", i === idx);
      li.classList.toggle("done", i < idx);
      const start = chs[i].start, end = chs[i + 1]?.start ?? current.duration;
      const p = i < idx ? 1 : i > idx ? 0 : (t - start) / Math.max(0.1, end - start);
      li.querySelector(".bar").style.setProperty("--p", p.toFixed(3));
    });
  }

  /* ---------- playback ---------- */
  // Speech is loud most of the time; stretch the envelope so the seam shows relief.
  function contrast(peaks) {
    if (!peaks?.length) return peaks;
    const sorted = [...peaks].sort((a, b) => a - b);
    const lo = sorted[Math.floor(sorted.length * 0.08)];
    const hi = sorted[Math.floor(sorted.length * 0.97)] || 1;
    return peaks.map((v) => Math.max(0.04, Math.min(1, (v - lo) / Math.max(0.05, hi - lo))));
  }

  function load(ep, autoplay = false) {
    if (!ep._stretched) { ep.peaks = contrast(ep.peaks); ep._stretched = true; }
    current = ep;
    audio.src = ep.audio;
    audio.playbackRate = store.get("wb.rate", 1);
    const resume = positions[keyOf(ep)];
    if (resume && resume < ep.duration - 5) {
      audio.addEventListener("loadedmetadata", () => { audio.currentTime = resume; }, { once: true });
    }
    $("play").disabled = false;
    app.dataset.state = "ready";
    renderEpisode();
    setMediaSession();
    if (autoplay) play();
  }

  function play() {
    audio.play().catch(() => { /* needs a user gesture; the button covers that */ });
  }

  function seek(t) {
    if (!current) return;
    audio.currentTime = Math.max(0, Math.min(current.duration - 0.2, t));
    updateProgress(); draw();
  }

  function savePosition() {
    if (!current) return;
    positions[keyOf(current)] = Math.floor(audio.currentTime);
    // keep only episodes that are still in the feed
    for (const k of Object.keys(positions)) if (!episodes.some((e) => keyOf(e) === k)) delete positions[k];
    store.set("wb.positions", positions);
  }

  function setMediaSession() {
    if (!("mediaSession" in navigator) || !current) return;
    navigator.mediaSession.metadata = new MediaMetadata({
      title: current.title,
      artist: "Wielerbulletin",
      album: current.label ? `${current.label}, ${fmtDay(current.date)}` : fmtDay(current.date),
      artwork: [
        { src: "icons/icon-512.png", sizes: "512x512", type: "image/png" },
        { src: "icons/icon-192.png", sizes: "192x192", type: "image/png" },
      ],
    });
    const ms = navigator.mediaSession;
    const handlers = {
      play: () => play(),
      pause: () => audio.pause(),
      seekbackward: (d) => seek(audio.currentTime - (d.seekOffset || 15)),
      seekforward: (d) => seek(audio.currentTime + (d.seekOffset || 15)),
      seekto: (d) => seek(d.seekTime),
      previoustrack: () => {
        const i = chapterIndexAt(audio.currentTime);
        const ch = current.chapters;
        seek(audio.currentTime - ch[i].start > 3 ? ch[i].start : ch[Math.max(0, i - 1)].start);
      },
      nexttrack: () => {
        const next = current.chapters[chapterIndexAt(audio.currentTime) + 1];
        if (next) seek(next.start);
      },
    };
    for (const [action, fn] of Object.entries(handlers)) {
      try { ms.setActionHandler(action, fn); } catch { /* unsupported action */ }
    }
  }

  function updatePositionState() {
    if (!("mediaSession" in navigator) || !current || !isFinite(audio.duration)) return;
    try {
      navigator.mediaSession.setPositionState({
        duration: audio.duration, playbackRate: audio.playbackRate, position: audio.currentTime,
      });
    } catch { /* ignore */ }
  }

  /* ---------- events ---------- */
  $("play").addEventListener("click", () => (audio.paused ? play() : audio.pause()));
  $("back").addEventListener("click", () => seek(audio.currentTime - 15));
  $("fwd").addEventListener("click", () => seek(audio.currentTime + 15));
  $("rate").addEventListener("click", () => {
    const next = RATES[(RATES.indexOf(audio.playbackRate) + 1) % RATES.length] || 1;
    audio.playbackRate = next;
    store.set("wb.rate", next);
    $("rate").textContent = `${String(next).replace(".", ",")}×`;
    updatePositionState();
  });
  $("rate").textContent = `${String(store.get("wb.rate", 1)).replace(".", ",")}×`;

  // drag anywhere on the seam to scrub (iOS range inputs only move by the thumb)
  const fractionAt = (e) => {
    const r = scrub.getBoundingClientRect();
    return Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
  };
  let dragging = false;
  scrub.addEventListener("pointerdown", (e) => {
    if (!current) return;
    dragging = true; scrub.setPointerCapture(e.pointerId);
    e.preventDefault(); seek(fractionAt(e) * current.duration);
  });
  scrub.addEventListener("pointermove", (e) => { if (dragging) seek(fractionAt(e) * current.duration); });
  scrub.addEventListener("pointerup", () => { dragging = false; savePosition(); });
  scrub.addEventListener("input", () => { if (!dragging && current) seek((scrub.value / 1000) * current.duration); });

  audio.addEventListener("play", () => {
    app.classList.add("is-playing");
    $("play").setAttribute("aria-label", "Pauzeren");
    kick();
  });
  audio.addEventListener("pause", () => {
    app.classList.remove("is-playing");
    $("play").setAttribute("aria-label", "Afspelen");
    savePosition(); kick();
  });
  audio.addEventListener("timeupdate", () => {
    if (audio.paused) { updateProgress(); draw(); }
    if (Math.floor(audio.currentTime) % 5 === 0) savePosition();
  });
  audio.addEventListener("loadedmetadata", updatePositionState);
  audio.addEventListener("ratechange", updatePositionState);
  audio.addEventListener("ended", () => {
    heard.add(keyOf(current));
    store.set("wb.heard", [...heard]);
    positions[keyOf(current)] = 0;
    store.set("wb.positions", positions);
    renderArchive();
  });
  audio.addEventListener("error", () => {
    $("footnote").textContent = "De audio kon niet worden geladen. Controleer je verbinding en probeer het opnieuw.";
  });

  document.addEventListener("keydown", (e) => {
    if (e.target.closest("button, input") && e.code === "Space") return;
    if (e.code === "Space") { e.preventDefault(); $("play").click(); }
  });
  addEventListener("resize", sizeCanvas);
  addEventListener("pagehide", savePosition);

  /* ---------- feed ---------- */
  async function init() {
    sizeCanvas();
    try {
      const res = await fetch(`feed.json?t=${Date.now()}`, { cache: "no-store" });
      if (!res.ok) throw new Error(res.status);
      const feed = await res.json();
      episodes = feed.episodes || [];
    } catch {
      episodes = [];
    }
    if (!episodes.length) {
      app.dataset.state = "empty";
      $("headline").textContent = "Het eerste bulletin verschijnt om acht uur";
      $("summary").textContent = "Elke ochtend vijf minuten wielernieuws, gelezen als een nieuwsbulletin.";
      $("dateline").textContent = fmtDay(todayIso());
      return;
    }
    load(mainEpisode(episodes));
    if (!episodes.some((e) => isDaily(e) && e.date === todayIso()) && new Date().getHours() >= 8) {
      $("footnote").textContent = "Het bulletin van vandaag is nog niet binnen. Je hoort hierboven het meest recente.";
    }
  }

  // a new bulletin may have landed while the app sat in the background
  document.addEventListener("visibilitychange", async () => {
    if (document.visibilityState !== "visible" || !audio.paused) return;
    try {
      const feed = await (await fetch(`feed.json?t=${Date.now()}`, { cache: "no-store" })).json();
      const next = feed.episodes?.length ? mainEpisode(feed.episodes) : null;
      if (next && (!episodes.length || keyOf(next) !== keyOf(mainEpisode(episodes))
                   || feed.episodes.length !== episodes.length)) {
        const wasCurrent = current;
        episodes = feed.episodes;
        // keep listening to a special if that is open; otherwise jump to the new bulletin
        if (wasCurrent && !isDaily(wasCurrent) && episodes.some((e) => keyOf(e) === keyOf(wasCurrent))) renderArchive();
        else load(next);
      }
    } catch { /* offline: keep what we have */ }
  });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
  init();
})();
