// Record VarScope's browser-local suggestion in headed WebGPU Chrome.
// Saves screencast frames plus, per phase, the texts and rects the captions use.
import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { Cdp, openPage, evaluate, sleep } from "./cdp.mjs";
import { launchHeaded } from "./headed.mjs";

const [url, out] = process.argv.slice(2);
const NODE = [857, 697];
mkdirSync(out, { recursive: true });
const child = launchHeaded();
const cdp = new Cdp(child);
const s = await openPage(cdp, url);
await cdp.send("Emulation.setDeviceMetricsOverride", { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false }, s);
await cdp.send("Page.bringToFront", {}, s);
await cdp.send("Emulation.setFocusEmulationEnabled", { enabled: true }, s);
await sleep(9000);
const ev = (js) => evaluate(cdp, s, `(() => { ${js} })()`);
await ev(`[...document.querySelectorAll('button')].find(b => /^SDTM.ADaM$/.test(b.textContent.trim())).click()`);
await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 420, y: 560 }, s);
await sleep(3000);

const PROBE = String.raw`
  const R = (e) => { if (!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; };
  const leaf = (re) => [...document.querySelectorAll('body *')].find(e => e.children.length === 0 && re.test(e.textContent.trim()));
  const inPanel = (re) => [...document.querySelectorAll('body *')].filter(e => re.test(e.textContent) && e.getBoundingClientRect().left > 1200 && e.getBoundingClientRect().width > 0).sort((a, b) => a.textContent.length - b.textContent.length)[0] || null;
  const top = document.body.innerText.match(/nodes\s*·\s*(\d+)[\s\S]*?edges\s*·\s*(\d+)[\s\S]*?mapped\s*·\s*(\d+\/\d+)/);
  const t = document.body.innerText;
  const i = t.indexOf('ADAM MAPPING');
  const panel = i >= 0 ? t.slice(i, i + 500).split('\n').map(x => x.trim()).filter(Boolean) : [];
  const model = inPanel(/browser\/Qwen/);
  const only = inPanel(/Proposal only/);
  const mapped = leaf(/^mapped/) || leaf(/mapped\s*·/);
  const pct = inPanel(/^\s*\d+%\s*$/);
  const target = pct ? pct.previousElementSibling || pct.parentElement : null;
  const progress = [...document.querySelectorAll('body *')].filter(e => e.children.length === 0 && /load|download|%|progress|model/i.test(e.textContent) && e.getBoundingClientRect().left > 1200).map(e => e.textContent.trim()).slice(0, 4);
  return JSON.stringify({
    domain: (t.match(/DOMAIN\s*\n\s*(\S+)/) || [])[1] || null,
    nodes: top && top[1], edges: top && top[2], mapped: top && top[3],
    selected: (leaf(/^AE\.AEACN$/) || {}).textContent || null,
    panel, model: model && model.textContent.trim(), proposalOnly: only && only.textContent.trim(),
    pct: pct && pct.textContent.trim(), target: target && target.textContent.trim(),
    rects: { model: R(model), only: R(only), mapped: R(mapped), pct: R(pct), target: R(target && target.parentElement) },
    progress,
  });`;

const frames = []; let n = 0; let polling = true; let paused = false;
const origOn = cdp._onData.bind(cdp);
cdp.read.removeAllListeners("data");
cdp.read.on("data", (chunk) => {
  const text = Buffer.concat([cdp.buf, chunk]).toString("utf8");
  for (const part of text.split("\0")) {
    if (!part.includes('"Page.screencastFrame"')) continue;
    try {
      const m = JSON.parse(part); const p = m.params; n += 1;
      const f = join(out, `s-${String(n).padStart(4, "0")}.jpg`);
      writeFileSync(f, Buffer.from(p.data, "base64"));
      frames.push({ file: f, t: p.metadata.timestamp, src: "cast" });
      cdp.write.write(JSON.stringify({ id: 900000 + n, method: "Page.screencastFrameAck", params: { sessionId: p.sessionId }, sessionId: m.sessionId }) + "\0");
    } catch { /* partial */ }
  }
  origOn(chunk);
});
const poller = (async () => {
  while (polling) {
    if (paused) { await sleep(20); continue; }
    const t1 = Date.now();
    try {
      const { data } = await cdp.send("Page.captureScreenshot", { format: "jpeg", quality: 88 }, s);
      n += 1;
      const f = join(out, `f-${String(n).padStart(4, "0")}.jpg`);
      writeFileSync(f, Buffer.from(data, "base64"));
      frames.push({ file: f, t: t1 / 1000 });
    } catch { /* a slow frame; take the next */ }
    const dt = Date.now() - t1;
    if (dt < 120) await sleep(120 - dt);
  }
})();
const phases = [];
const mark = async (name) => { const st = JSON.parse(await ev(PROBE)); st.name = name; st.t = Date.now() / 1000; phases.push(st); console.log(name, JSON.stringify({ mapped: st.mapped, pct: st.pct, target: st.target, model: st.model, progress: st.progress }).slice(0, 300)); };
const click = async ([x, y]) => {
  paused = true; await sleep(250);
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y }, s); await sleep(150);
  await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 }, s); await sleep(70);
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 }, s);
  await sleep(150); paused = false;
};

await cdp.send("Page.startScreencast", { format: "jpeg", quality: 90, everyNthFrame: 1 }, s);
const t0 = Date.now() / 1000;
await mark("overview");
await sleep(3500);
await click(NODE); await sleep(900); await mark("selected");
await sleep(2600);
const sug = JSON.parse(await ev(`const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Suggest mapping'); if(!b) return JSON.stringify(null); const r=b.getBoundingClientRect(); return JSON.stringify([r.left+r.width/2, r.top+r.height/2]);`));
await click(sug); await sleep(700); await mark("reasoning");
const tw = Date.now();
const timeline = [];
while (Date.now() - tw < 240000) {
  const txt = await ev(`const t=document.body.innerText; const i=t.indexOf('ADAM MAPPING'); const j=t.indexOf('CONNECTED NODES'); return i>=0 ? t.slice(i+13, j>i ? j : i+300).replace(/\\s+/g,' ').trim() : ''`);
  if (!timeline.length || timeline.at(-1).text !== txt) timeline.push({ t: Date.now() / 1000, text: txt });
  if (/Proposal only|No mapping proposed/.test(txt)) break;
  await sleep(300);
}
await sleep(400); await mark("proposal");
await sleep(6000);
polling = false; await poller;
await cdp.send("Page.stopScreencast", {}, s); await sleep(300);
frames.sort((a, b) => a.t - b.t);
writeFileSync(join(out, "frames.json"), JSON.stringify(frames));
writeFileSync(join(out, "phases.json"), JSON.stringify({ t0, suggestButton: sug, node: NODE, phases, timeline }, null, 1));
console.log("timeline", timeline.length, JSON.stringify(timeline.map(x => x.text.slice(0, 60))).slice(0, 900));
console.log("frames", frames.length, "span", frames.length ? (frames.at(-1).t - frames[0].t).toFixed(1) : 0, "reasoning took", (phases[3].t - phases[2].t).toFixed(1));
child.kill("SIGKILL");
process.exit(0);
