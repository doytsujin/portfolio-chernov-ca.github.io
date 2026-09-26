// Headed Chrome with the flags that give WebGPU a real GPU adapter over Vulkan
// (headless gets a software adapter, far too slow for the model). Kept awake
// while occluded so a background recording does not stall.
import { spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

export function launchHeaded(w = 1600, h = 1000) {
  return spawn("google-chrome", [
    "--enable-unsafe-webgpu", "--use-angle=vulkan",
    "--enable-features=Vulkan,VulkanFromANGLE,DefaultANGLEVulkan", "--ignore-gpu-blocklist",
    "--no-first-run", "--no-default-browser-check", "--disable-extensions",
    "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding", "--disable-background-timer-throttling",
    `--user-data-dir=${mkdtempSync(join(tmpdir(), "vs-"))}`, "--remote-debugging-pipe",
    `--window-size=${w},${h}`, "--new-window", "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe", "pipe", "pipe"] });
}
