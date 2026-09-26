// Record the live Admission showcase and, for every state, the texts and
// viewport rects the side notes will quote and point at.
import { writeFileSync, mkdirSync, mkdtempSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { findChrome, launchChrome, Cdp, openPage, evaluate, sleep } from "./cdp.mjs";

const out = process.argv[2];
const W = 1080, H = 860, HOLD = 3.5;
const STEPS = [
  [null, null],
  ["principal", "Analyst"],
  ["principal", "Clinical reviewer"],
  ["principal", "External auditor"],
  ["principal", "Process engineer"],
  ["request", "Calculate the yield for batch B003"],
  ["request", "Detect outliers in batch recovery"],
  ["principal", "Analyst"],
];
mkdirSync(out, { recursive: true });
const child = launchChrome(findChrome(), mkdtempSync(join(tmpdir(), "rp-")));
const cdp = new Cdp(child);
const s = await openPage(cdp, "https://agenticdatasets.org/showcase/?r=" + Date.now());
await cdp.send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 1, mobile: false }, s);
await sleep(5000);
const ev = (js) => evaluate(cdp, s, `(() => { ${js} })()`);
await ev(`[...document.querySelectorAll('button')].forEach(b => { if (b.textContent.trim() === 'Light') b.click(); });`);
await ev(`const h = document.querySelector('#admission'); window.scrollTo(0, h.getBoundingClientRect().top + scrollY + 40);`);
await sleep(800);

// Everything the notes say is read off the page here.
const PROBE = String.raw`
  const A = document.querySelector('#admission');
  const R = (e) => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; };
  const dark = (b) => { const c = (getComputedStyle(b).backgroundColor.match(/[\d.]+/g) || []).map(Number); const a = c.length > 3 ? c[3] : 1; return a > 0.5 && c[0] + c[1] + c[2] < 150; };
  const btns = [...A.querySelectorAll('button')];
  const pb = btns.find(b => dark(b) && /clearance/.test(b.textContent));
  const obsHead = [...A.querySelectorAll('*')].find(e => e.children.length === 0 && e.textContent.trim().toUpperCase() === 'OBSERVATION');
  const obs = obsHead.parentElement;
  const chip = [...obs.querySelectorAll('*')].find(e => e.children.length === 0 && /^(GRANTED|REFUSED|INDETERMINATE)$/.test(e.textContent.trim()));
  const chipRow = chip.parentElement;
  const rowOf = (label) => { const k = [...obs.querySelectorAll('*')].find(e => e.children.length === 0 && e.textContent.trim() === label); return k; };
  const val = (label) => { const k = rowOf(label); if (!k) return null; const n = k.nextElementSibling || k.parentElement.nextElementSibling; return n ? n.textContent.trim() : null; };
  const flags = [...obs.querySelectorAll('*')].filter(e => e.children.length === 0 && /^(granted|executed|result|cache hit)$/.test(e.textContent.trim()));
  const evid = [...obs.querySelectorAll('*')].find(e => /^evidence/.test(e.textContent.trim()) && e.textContent.trim().length < 30);
  const input = A.querySelector('input, textarea') || [...A.querySelectorAll('*')].find(e => e.children.length === 0 && e.textContent.trim() === document.querySelector('#admission button.active, #admission button')?.textContent);
  const reqBox = [...A.querySelectorAll('*')].find(e => e.children.length === 0 && e.textContent.trim().toUpperCase() === 'REQUEST').nextElementSibling;
  return JSON.stringify({
    principal: pb.firstChild ? pb.childNodes[0].textContent.trim() : pb.textContent.trim(),
    principalNote: pb.childNodes.length > 1 ? pb.childNodes[1].textContent.trim() : '',
    principalRect: R(pb),
    request: reqBox.value || reqBox.textContent.trim(), requestRect: R(reqBox),
    verdict: chip.textContent.trim(), chipParts: [...chipRow.children].map(e => e.textContent.trim()).filter(Boolean), chipRowText: [...chipRow.children].map(e => e.textContent.trim()).join(' | '), chipRect: R(chipRow),
    capability: val('capability'), admitted: val('admitted scope'), executedScope: val('executed scope'),
    flagsRect: flags.length ? R(flags[0].parentElement) : null,
    flags: flags.map(f => [f.textContent.trim(), (f.previousElementSibling || f.parentElement).textContent.includes('■') || getComputedStyle(f).color]),
    admittedRect: rowOf('admitted scope') ? R(rowOf('admitted scope').parentElement) : null,
    evidence: evid ? evid.textContent.trim() : null, evidenceRect: evid ? R(evid) : null,
  });`;

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
      const f = join(out, `f-${String(n).padStart(4, "0")}.jpg`);
      writeFileSync(f, Buffer.from(p.data, "base64"));
      frames.push({ file: f, t: p.metadata.timestamp });
      cdp.write.write(JSON.stringify({ id: 900000 + n, method: "Page.screencastFrameAck", params: { sessionId: p.sessionId }, sessionId: m.sessionId }) + "\0");
    } catch { /* partial */ }
  }
  origOn(chunk);
});
await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, everyNthFrame: 1 }, s);
const click = (label) => ev(`const b = [...document.querySelectorAll('#admission button')].find(x => x.textContent.trim().startsWith(${JSON.stringify(label)})); if (b) b.click(); return !!b;`);

const states = [];
const t0 = Date.now();
for (let i = 0; i < STEPS.length; i++) {
  while (Date.now() - t0 < i * HOLD * 1000) await sleep(20);
  const [, label] = STEPS[i];
  const tClick = Date.now() / 1000;
  if (label) { const ok = await click(label); if (!ok) throw new Error("no button " + label); }
  await sleep(500);
  const st = JSON.parse(await ev(PROBE));
  st.t = tClick;
  states.push(st);
  console.log(i, st.principal, "|", st.request, "|", st.chipRowText, "|", st.capability, "|", st.admitted);
}
while (Date.now() - t0 < STEPS.length * HOLD * 1000) await sleep(20);
await cdp.send("Page.stopScreencast", {}, s);
await sleep(300);
writeFileSync(join(out, "frames.json"), JSON.stringify(frames));
writeFileSync(join(out, "states.json"), JSON.stringify({ hold: HOLD, t0: t0 / 1000, W, H, states }, null, 1));
console.log("frames", frames.length, "first frame t", frames[0]?.t, "t0", t0 / 1000);
child.kill("SIGKILL");
process.exit(0);
