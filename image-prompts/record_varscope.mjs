// Record the mapping tool's browser-local suggestion as KEYFRAMES: one clean
// screenshot per state the detail panel passes through, taken live. A shot is
// kept only if the panel text is the same before and after the capture, so
// every keyframe is labelled with the state it actually shows. Timings are the
// real ones, recorded beside each keyframe.
//
//   node record_varscope.mjs <url> <outDir>
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

// Panel text between ADAM MAPPING and CONNECTED NODES, plus what the cards quote.
const PANEL = String.raw`
  const t = document.body.innerText;
  const i = t.indexOf('ADAM MAPPING'), j = t.indexOf('CONNECTED NODES');
  return JSON.stringify(i >= 0 ? t.slice(i + 13, j > i ? j : i + 300).replace(/\s+/g, ' ').trim() : '');`;
const PROBE = String.raw`
  const t = document.body.innerText;
  const R = (e) => { if (!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; };
  const inPanel = (re) => [...document.querySelectorAll('body *')].filter(e => re.test(e.textContent) && e.getBoundingClientRect().left > 1200 && e.getBoundingClientRect().width > 0).sort((a, b) => a.textContent.length - b.textContent.length)[0] || null;
  const top = t.match(/nodes\s*·\s*(\d+)[\s\S]*?edges\s*·\s*(\d+)[\s\S]*?mapped\s*·\s*(\d+\/\d+)/);
  const head = inPanel(/^\s*ADAM MAPPING\s*$/i);
  const pct = inPanel(/^\s*\d+%\s*$/);
  const model = inPanel(/browser\/Qwen/);
  const only = inPanel(/^\s*Proposal only/);
  return JSON.stringify({
    selected: (t.match(/\n(AE\.[A-Z]+)\n\s*VARIABLE/) || [])[1] || null,
    domain: (t.match(/DOMAIN\s*\n\s*(\S+)/) || [])[1] || null,
    nodes: top && top[1], edges: top && top[2], mapped: top && top[3],
    pct: pct && pct.textContent.trim(),
    target: pct && pct.previousElementSibling ? pct.previousElementSibling.textContent.trim() : null,
    model: model && model.textContent.trim(),
    rects: { head: R(head), pct: R(pct), target: R(pct && pct.parentElement), model: R(model), only: R(only) },
  });`;

const keys = [];
const shoot = async (name) => {
  for (let tries = 0; tries < 6; tries++) {
    const before = JSON.parse(await ev(PANEL));
    const t = Date.now() / 1000;
    const { data } = await cdp.send("Page.captureScreenshot", { format: "png" }, s);
    const after = JSON.parse(await ev(PANEL));
    if (before === after) {
      const f = join(out, `k-${String(keys.length + 1).padStart(2, "0")}.png`);
      writeFileSync(f, Buffer.from(data, "base64"));
      const st = JSON.parse(await ev(PROBE));
      keys.push({ name, file: f, t, panel: after, ...st });
      console.log(name.padEnd(10), after.slice(0, 70));
      return after;
    }
  }
  return null;
};
const click = async ([x, y]) => {
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y }, s); await sleep(150);
  await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 }, s); await sleep(70);
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 }, s);
};

await shoot("overview");
await click(NODE); await sleep(1500);
await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 420, y: 560 }, s); await sleep(400);
await shoot("selected");
const sug = JSON.parse(await ev(`const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Suggest mapping'); const r=b.getBoundingClientRect(); return JSON.stringify([r.left+r.width/2, r.top+r.height/2]);`));
const tClick = Date.now() / 1000;
await click(sug);
await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 420, y: 560 }, s);
let last = "";
const tw = Date.now();
while (Date.now() - tw < 240000) {
  const cur = JSON.parse(await ev(PANEL));
  if (cur !== last) {
    const name = /^Loading model/.test(cur) ? "loading" : /^Reasoning/.test(cur) ? "reasoning" : /Proposal only|No mapping proposed/.test(cur) ? "proposal" : "other";
    const got = await shoot(name);
    last = got ?? cur;
    if (name === "proposal") break;
  }
  await sleep(120);
}
writeFileSync(join(out, "keys.json"), JSON.stringify({ node: NODE, suggest: sug, tClick, keys }, null, 1));
console.log("keyframes", keys.length);
child.kill("SIGKILL");
process.exit(0);
