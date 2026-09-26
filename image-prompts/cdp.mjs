// Minimal Chrome DevTools Protocol client over --remote-debugging-pipe, used by
// record_admission.mjs. No debug port is bound.

import { spawn, execFileSync } from "node:child_process";

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** First working Chrome/Chromium on PATH (or $CHROME_BIN). Throws if none. */
export function findChrome() {
  const candidates = [
    process.env.CHROME_BIN,
    "google-chrome",
    "google-chrome-stable",
    "chromium-browser",
    "chromium",
  ].filter(Boolean);
  for (const c of candidates) {
    try {
      execFileSync(c, ["--version"], { stdio: "ignore" });
      return c;
    } catch {
      /* not this one */
    }
  }
  throw new Error("no Chrome/Chromium found (set CHROME_BIN)");
}

/** Launch headless Chrome wired for a CDP pipe (fds 3=in, 4=out). */
export function launchChrome(chrome, profileDir) {
  return spawn(
    chrome,
    [
      "--headless=new",
      "--no-sandbox",
      "--disable-gpu",
      "--disable-dev-shm-usage",
      "--no-first-run",
      "--no-default-browser-check",
      `--user-data-dir=${profileDir}`,
      "--remote-debugging-pipe",
      "--window-size=1280,900",
    ],
    { stdio: ["ignore", "ignore", "pipe", "pipe", "pipe"] },
  );
}

/** Minimal CDP client over the browser's NUL-framed JSON pipe (fds 3/4). */
export class Cdp {
  constructor(child) {
    this.write = child.stdio[3]; // browser reads here
    this.read = child.stdio[4]; // browser writes here
    this.id = 0;
    this.pending = new Map();
    this.buf = Buffer.alloc(0);
    this.read.on("data", (chunk) => this._onData(chunk));
  }
  _onData(chunk) {
    this.buf = Buffer.concat([this.buf, chunk]);
    let nul;
    while ((nul = this.buf.indexOf(0)) !== -1) {
      const msg = this.buf.subarray(0, nul).toString("utf8");
      this.buf = this.buf.subarray(nul + 1);
      if (!msg) continue;
      let obj;
      try {
        obj = JSON.parse(msg);
      } catch {
        continue;
      }
      if (obj.id != null && this.pending.has(obj.id)) {
        const { resolve, reject } = this.pending.get(obj.id);
        this.pending.delete(obj.id);
        obj.error ? reject(new Error(obj.error.message)) : resolve(obj.result);
      }
    }
  }
  send(method, params = {}, sessionId) {
    const id = ++this.id;
    const payload = { id, method, params };
    if (sessionId) payload.sessionId = sessionId;
    this.write.write(JSON.stringify(payload) + "\0");
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      setTimeout(() => {
        if (this.pending.delete(id)) reject(new Error(`CDP timeout: ${method}`));
      }, 30_000);
    });
  }
}

/** Open `url` in a fresh page target with a flat session; enable Page+Runtime. */
export async function openPage(cdp, url) {
  const { targetId } = await cdp.send("Target.createTarget", { url });
  const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
  await cdp.send("Page.enable", {}, sessionId);
  await cdp.send("Runtime.enable", {}, sessionId);
  return sessionId;
}

/** Evaluate an expression in the page, returning its (by-value) result. */
export async function evaluate(cdp, sessionId, expression) {
  const r = await cdp.send(
    "Runtime.evaluate",
    { expression, returnByValue: true, awaitPromise: false },
    sessionId,
  );
  return r?.result?.value;
}
