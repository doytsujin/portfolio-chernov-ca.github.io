// Record the semantic gateway's static browser build, full frame, with hint
// cards laid over it: node record_gateway.mjs <url> <outdir>
//
// The UI is recorded live -- a CDP screencast, not keyframes -- and driven the
// way a person would: a drawn cursor moves and clicks, queries are typed one
// character at a time. Every number a hint quotes is read off the page when
// the hint appears.
//
// The demo corpus is pseudonymised (people, sites, labs and entity names are
// invented), but its records still carry record ids and serial and asset
// numbers -- so every record body is removed, including the ones the app
// truncates before the serial -- and the toolbar carries the product's
// internal name. What to hide is read from redact.local.json, which is kept
// out of the repository because it names what it hides. A script injected
// before the app loads removes any element that spells one of those before it is
// painted, and a guard polls the page during the recording and fails the run
// if anything matching is visible. compose_gateway.py then reads the rendered
// frames with OCR, because a DOM check cannot see what was actually drawn.
import { writeFileSync, mkdirSync, mkdtempSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { findChrome, launchChrome, Cdp, openPage, sleep } from "./cdp.mjs";

const [url, out] = process.argv.slice(2);
if (!url || !out) throw new Error("usage: node record_gateway.mjs <url> <outdir>");
const W = 1600, H = 1000;
const HERE = dirname(fileURLToPath(import.meta.url));
const font = (f) => readFileSync(join(HERE, "fonts", f)).toString("base64");

// Shared with the OCR check in compose_gateway.py.
const LIST = process.env.REDACT_FILE || join(HERE, "redact.local.json");
let redact;
try { redact = JSON.parse(readFileSync(LIST, "utf8")); }
catch { throw new Error(`refusing: no redaction list at ${LIST} -- it is kept out of the repository, so it has to be present locally`); }
const REDACT = `new RegExp(${JSON.stringify(redact.patterns.join("|"))}, "i")`;
const TAGRE = `new RegExp(${JSON.stringify(redact.tag)}, "i")`;

const INIT = String.raw`(() => {
  const RE = ${REDACT};
  const TAG = ${TAGRE};   // provenance tags on capabilities
  const mine = (el) => el.closest && el.closest('#__cap');
  const hide = (el) => {
    el.dataset.redacted = '1';
    // The toolbar wordmark keeps its box, so the toolbar does not shift.
    if (el.closest('header')) el.style.setProperty('visibility', 'hidden', 'important');
    else el.style.setProperty('display', 'none', 'important');
  };
  // Hide the deepest element whose text matches -- deepest, so text split
  // across child elements is still caught by the parent that joins it.
  const scan = (root) => {
    if (!root || root.nodeType !== 1 || mine(root)) return;
    for (const el of [root, ...root.querySelectorAll('*')]) {
      if (el.dataset.redacted || mine(el)) continue;
      const t = el.textContent || '';
      if (el.children.length === 0 && TAG.test(t.trim())) { hide(el); continue; }
      if (!RE.test(t)) continue;
      if ([...el.children].some((c) => RE.test(c.textContent || ''))) continue;
      hide(el);
    }
  };
  new MutationObserver((ms) => {
    for (const m of ms) scan(m.target.nodeType === 1 ? m.target : m.target.parentElement);
  }).observe(document, { subtree: true, childList: true, characterData: true });

  window.__leaks = () => {
    const out = [];
    for (const el of document.body.querySelectorAll('*')) {
      if (mine(el)) continue;
      const t = el.textContent || '';
      if (!RE.test(t) || [...el.children].some((c) => RE.test(c.textContent || ''))) continue;
      if (!el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) continue;
      const r = el.getBoundingClientRect();
      if (r.width && r.height && r.right > 0 && r.bottom > 0 && r.left < innerWidth && r.top < innerHeight)
        out.push(t.trim().slice(0, 60));
    }
    return out;
  };

  // Type sized for the portfolio page, where the clip plays at about half scale.
  const css = ${"`"}
    @font-face { font-family: CapSlab; font-weight: 400; src: url(data:font/ttf;base64,${font("RobotoSlab-Regular.ttf")}); }
    @font-face { font-family: CapSlab; font-weight: 700; src: url(data:font/ttf;base64,${font("RobotoSlab-Bold.ttf")}); }
    @font-face { font-family: CapMono; src: url(data:font/ttf;base64,${font("NerdMono.ttf")}); }
    #__cap { position: fixed; inset: 0; pointer-events: none; z-index: 2147483647; }
    #__cap .hint { position: absolute; top: 56px; right: 16px; width: 432px; background: #fff;
      border: 1px solid #cbd5e1; border-radius: 12px; padding: 18px 22px 18px 26px;
      box-shadow: 0 10px 30px rgba(15,23,42,.14); transition: opacity .35s ease, transform .35s ease; }
    #__cap .hint::before { content: ""; position: absolute; left: 0; top: 12px; bottom: 12px;
      width: 4px; border-radius: 2px; background: #dc2626; }
    #__cap .hint.off { opacity: 0; transform: translateY(-6px); }
    #__cap .eb { font: 14px/1.2 CapMono, monospace; letter-spacing: .12em; color: #475569; }
    #__cap .ti { font: 700 27px/1.22 CapSlab, Georgia, serif; color: #0f172a; margin-top: 8px; }
    #__cap .bo { font: 400 19px/1.42 CapSlab, Georgia, serif; color: #475569; margin-top: 8px; }
    #__cap .ft { font: 13px/1.3 CapMono, monospace; color: #64748b; margin-top: 12px;
      padding-top: 10px; border-top: 1px solid #e2e8f0; }
    #__cap .cur { position: absolute; left: 0; top: 0; width: 22px; height: 22px;
      transform: translate(-2px, -2px); filter: drop-shadow(0 1px 1px rgba(0,0,0,.35)); }
    #__cap .ring { position: absolute; width: 34px; height: 34px; margin: -17px 0 0 -17px;
      border: 2px solid #dc2626; border-radius: 50%; opacity: 0; }
    #__cap .ring.go { animation: capring .5s ease-out; }
    @keyframes capring { from { opacity: .9; transform: scale(.4); } to { opacity: 0; transform: scale(1.3); } }
  ${"`"};
  const mount = () => {
    const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
    const cap = document.createElement('div'); cap.id = '__cap';
    cap.innerHTML = '<div class="hint off"><div class="eb"></div><div class="ti"></div><div class="bo"></div><div class="ft"></div></div>'
      + '<div class="ring"></div>'
      + '<svg class="cur" viewBox="0 0 22 22"><path d="M2 2 L2 17 L6.5 12.8 L9.6 19.6 L12.3 18.4 L9.3 11.8 L15.3 11.6 Z" fill="#0f172a" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg>';
    document.body.appendChild(cap);
    const cur = cap.querySelector('.cur'), ring = cap.querySelector('.ring');
    cur.style.left = '1260px'; cur.style.top = '560px';
    addEventListener('mousemove', (e) => { cur.style.left = e.clientX + 'px'; cur.style.top = e.clientY + 'px'; }, true);
    addEventListener('mousedown', (e) => {
      ring.style.left = e.clientX + 'px'; ring.style.top = e.clientY + 'px';
      ring.classList.remove('go'); void ring.offsetWidth; ring.classList.add('go');
    }, true);
    window.__hint = (h) => {
      const box = cap.querySelector('.hint');
      if (!h) { box.classList.add('off'); return; }
      box.querySelector('.eb').textContent = h.eyebrow;
      box.querySelector('.ti').textContent = h.title;
      box.querySelector('.bo').innerHTML = h.body;
      box.querySelector('.ft').textContent = h.foot;
      box.classList.remove('off');
    };
  };
  if (document.body) mount(); else addEventListener('DOMContentLoaded', mount);
})();`;

mkdirSync(out, { recursive: true });
const child = launchChrome(findChrome(), mkdtempSync(join(tmpdir(), "gw-")));
const cdp = new Cdp(child);
const s = await openPage(cdp, "about:blank");
await cdp.send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 1, mobile: false }, s);
await cdp.send("Page.addScriptToEvaluateOnNewDocument", { source: INIT }, s);
await cdp.send("Page.navigate", { url }, s);

const ev = async (js) => {
  const r = await cdp.send("Runtime.evaluate", { expression: js, returnByValue: true, awaitPromise: true }, s);
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
  return r.result?.value;
};
const waitFor = async (js, ms = 30000) => {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { if (await ev(js)) return; await sleep(150); }
  throw new Error("timed out waiting for " + js);
};

// ── input, as a person would give it ────────────────────────────────────────
let cx = 1260, cy = 560;
// Paced by the clock, not by a step count: each step is a CDP round trip, so
// a fixed count ran half again as long as asked.
const move = async (x, y, ms = 600) => {
  const x0 = cx, y0 = cy, t0 = Date.now();
  for (;;) {
    const k = Math.min(1, (Date.now() - t0) / ms), e = k < .5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2;
    cx = x0 + (x - x0) * e; cy = y0 + (y - y0) * e;
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: cx, y: cy }, s);
    if (k >= 1) return;
    await sleep(10);
  }
};
const press = async () => {
  for (const type of ["mousePressed", "mouseReleased"])
    await cdp.send("Input.dispatchMouseEvent", { type, x: cx, y: cy, button: "left", clickCount: 1 }, s);
};
const centre = async (js) => {
  const r = await ev(`(() => { const e = ${js}; if (!e) return null; const b = e.getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; })()`);
  if (!r) throw new Error("no element: " + js);
  return r;
};
const clickOn = async (js, ms) => { const [x, y] = await centre(js); await move(x, y, ms); await sleep(120); await press(); };
const typeText = async (text) => {
  for (const ch of text) { await cdp.send("Input.insertText", { text: ch }, s); await sleep(45); }
};
const enter = async () => {
  for (const type of ["keyDown", "keyUp"])
    await cdp.send("Input.dispatchKeyEvent", { type, key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 }, s);
};
const wheel = async (x, y, dy, steps = 6) => {
  for (let i = 0; i < steps; i++) {
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseWheel", x, y, deltaX: 0, deltaY: dy / steps }, s);
    await sleep(60);
  }
};
const btn = (pred) => `[...document.querySelectorAll('button')].find(b => ${pred})`;
const hint = (h) => ev(`window.__hint(${JSON.stringify(h)})`);
const FOOT = "static browser build · pseudonymised corpus";

// ── screencast ──────────────────────────────────────────────────────────────
const frames = [];
let n = 0;
const origOn = cdp._onData.bind(cdp);
cdp.read.removeAllListeners("data");
cdp.read.on("data", (chunk) => {
  const text = Buffer.concat([cdp.buf, chunk]).toString("utf8");
  for (const part of text.split("\0")) {
    if (!part.includes('"Page.screencastFrame"')) continue;
    try {
      const m = JSON.parse(part); const p = m.params; n += 1;
      const f = join(out, `f-${String(n).padStart(5, "0")}.jpg`);
      writeFileSync(f, Buffer.from(p.data, "base64"));
      frames.push({ file: f, t: p.metadata.timestamp });
      cdp.write.write(JSON.stringify({ id: 900000 + n, method: "Page.screencastFrameAck", params: { sessionId: p.sessionId }, sessionId: m.sessionId }) + "\0");
    } catch { /* partial message; the next chunk completes it */ }
  }
  origOn(chunk);
});

await waitFor(`document.querySelectorAll('button').length > 3 && !!window.__hint`);
await sleep(8000);   // the graph settles and the embedding model loads

// Facts the hints quote, read off the page.
const docs = await ev(`(() => { const m = document.body.textContent.match(/of (\\d+) carry one/); return m ? Number(m[1]).toLocaleString('en-US') : null })()`);
const lenses = await ev(`[...document.querySelectorAll('button')].filter(b => b.getBoundingClientRect().y > ${H - 70}).map(b => b.innerText.trim()).filter(Boolean)`);
if (!docs || lenses.length < 4) throw new Error(`could not read the page: docs=${docs} lenses=${lenses}`);

const leaks = [];
let guarding = true;
const guard = (async () => {
  while (guarding) {
    const l = await ev(`window.__leaks()`);
    if (l.length) leaks.push({ t: Date.now() / 1000, l });
    await sleep(120);
  }
})();

const states = [];
const mark = (name) => { states.push({ name, t: Date.now() / 1000 }); console.log("state", name); };

// 1. What this is. The card is up before the first frame.
await hint({ eyebrow: "SEMANTIC GATEWAY", title: "One index, four surfaces",
  body: `${docs} lab-asset records, indexed in this browser tab. Search, chat, the graph and MCP all read the same index.`, foot: FOOT });
await sleep(500);
await cdp.send("Page.startScreencast", { format: "jpeg", quality: 90, everyNthFrame: 1, maxWidth: W, maxHeight: H }, s);
await sleep(200);
mark("intro");
await move(1000, 470, 800);
await move(760, 330, 900);
await sleep(1400);

// 2. Search.
mark("search");
await hint({ eyebrow: "SEARCH", title: "Ask in words",
  body: "A natural-language query over the index. The graph dims to what it found.", foot: FOOT });
await move(800, 60, 700);
await sleep(500);
await clickOn(`document.querySelector('textarea')`, 300);
await typeText("centrifuges due for calibration");
await sleep(300);
await enter();
await waitFor(`/Search hits \\(\\d+\\)/.test(document.body.innerText)`);
const hits = await ev(`document.body.innerText.match(/Search hits \\((\\d+)\\)/)[1]`);
await sleep(600);
await hint({ eyebrow: "SEARCH", title: `${hits} hits, on the graph`,
  body: "Each hit also lists the capabilities its source publishes: the tools an agent can call on it.", foot: FOOT });
await move(170, 560, 800);
await sleep(2600);
await move(800, 60, 700);
await sleep(300);
await clickOn(btn(`b.innerText.trim() === 'Clear all'`), 400);
await sleep(500);
if (await ev(`/Search hits \\(\\d+\\)/.test(document.body.innerText)`))
  await clickOn(btn(`b.title === 'Dismiss'`), 600);
await move(900, 600, 600);
await sleep(700);

// 3. Grounded chat.
mark("chat");
await hint({ eyebrow: "GROUNDED CHAT", title: "Answers cite their records",
  body: "This build has no language model. It answers from the records' own fields, and says so.", foot: FOOT });
await clickOn(btn(`b.title === 'Chat with the corpus'`), 900);
await sleep(700);
await clickOn(`document.querySelector('textarea[placeholder^="Ask"]')`, 400);
await typeText("Where is Freezer H-8983?");
await sleep(300);
await enter();
await waitFor(`/SOURCES \\(\\d+\\)/i.test(document.body.innerText)`);
const cites = await ev(`document.body.innerText.match(/SOURCES \\((\\d+)\\)/i)[1]`);
await sleep(600);
await hint({ eyebrow: "GROUNDED CHAT", title: "Answers cite their records",
  body: `Location and lab come from the record's own fields, with ${cites} cited sources. There is no language model in this build.`, foot: FOOT });
await clickOn(btn(`/^\\[1\\]/.test(b.innerText.trim())`), 800);
await sleep(3000);
await clickOn(btn(`b.title === 'Close' && b.getBoundingClientRect().x > ${W / 2}`), 700);
await sleep(800);

// 4. The knowledge graph, through its lenses.
mark("graph");
const shown = lenses.slice(0, 6).join(", ");
await hint({ eyebrow: "KNOWLEDGE GRAPH", title: "One graph, many lenses",
  body: `Every lens is a field the records carry: ${shown}, and more. The ontology is read from the data.`, foot: FOOT });
for (const l of ["lab", "status", "similarity"]) {
  await clickOn(btn(`b.innerText.trim() === '${l}' && b.getBoundingClientRect().y > ${H - 70}`), 700);
  await sleep(l === "similarity" ? 900 : 2300);
}

// 5. MCP.
mark("mcp");
await move(6, 500, 900);
await press();
await sleep(900);
await clickOn(btn(`b.title === 'Open bucket detail'`), 700);
await sleep(900);
await waitFor(`[...document.querySelectorAll('div')].some(d => /^Capabilities from this bucket/.test(d.textContent.trim()))`);
const caps = await ev(`[...document.querySelectorAll('div')].find(d => /^Capabilities from this bucket/.test(d.textContent.trim())).textContent.match(/\\((\\d+)\\)/)[1]`);
const names = await ev(`[...document.querySelectorAll('span,div')].filter(e => e.children.length === 0 && /^(get|find|same)_[a-z_]+$/.test(e.textContent.trim())).map(e => e.textContent.trim()).filter((v, i, a) => a.indexOf(v) === i).slice(0, 4)`);
await hint({ eyebrow: "MCP", title: "Tools for Copilot and any MCP client",
  body: `This source publishes ${caps} capabilities, among them ${names.slice(0, -1).join(", ")} and ${names.at(-1)}.`, foot: FOOT });
await move(800, 620, 600);
await wheel(800, 620, 900, 8);
await sleep(3800);
mark("end");

await cdp.send("Page.stopScreencast", {}, s);
guarding = false;
await guard;
await sleep(300);
writeFileSync(join(out, "frames.json"), JSON.stringify(frames));
writeFileSync(join(out, "states.json"), JSON.stringify({ W, H, docs, hits, cites, caps, lenses, states }, null, 1));
console.log(`frames ${frames.length}  docs ${docs}  hits ${hits}  cites ${cites}  caps ${caps}`);
child.kill("SIGKILL");
if (leaks.length) {
  console.error("REFUSING: visible text matched the redaction pattern during the recording:");
  for (const x of leaks.slice(0, 10)) console.error(" ", x.t.toFixed(2), JSON.stringify(x.l));
  process.exit(1);
}
process.exit(0);
