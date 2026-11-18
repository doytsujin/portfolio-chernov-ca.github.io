# Every Stage Reported Success. The Data Was Wrong.

*By [Alexander Chernov](https://www.linkedin.com/in/thedoytsujin/). First published on LinkedIn, 2026-08-16. [Read the original](https://www.linkedin.com/pulse/every-stage-reported-success-data-wrong-alexander-chernov-yablc/).*

---

![Four pipeline stages — transfer, decode, map, write — each reporting success, over a band of the data they actually produced: a transfer four bytes short, every latitude zeroed, heart rate absent, and an activity type that was assumed rather than read. The checks that would normally catch this — success codes, schema and null checks, row counts, the pipeline's own tests — all passed. What caught each one was the same quantity measured a second time by a route the pipeline never took.](every-stage-reported-success/banner_16x9.webp)

The failure mode I fear most in a data pipeline is not the one that pages you at 3am. It is the one where every stage returns cleanly, every row count looks sane, every dashboard renders — and the numbers are wrong in a way that is perfectly plausible.

I spent a few days recovering five years of running data off a discontinued GPS watch. It was meant to be a weekend errand. What it turned into was an unusually clean study of that failure mode, because the pipeline lied to me **four separate times**, and not once did anything throw.

Every one of those four was caught by the same kind of thing: a check that measured the data a *different way* than the pipeline produced it. None was caught by an error code, a schema, a type check, or a test that the pipeline wrote about itself.

That is the whole article. The watch is just the vehicle.

## The setup, briefly

Epson sold GPS running watches, then shut the sync service down on 31 March 2025. The watch still works. Its data is still on it. The supported way to get that data off no longer exists.

Over USB the watch is not a mass-storage device — it is a vendor command protocol tunnelled over HID reports, with no published specification. Over Bluetooth LE it speaks a custom GATT protocol with its own framing and flow control, at about 180 bytes per second. I recovered both from the Android app, and the BLE path is the one that works end to end: 23 activities, roughly 2.1 MB, downloaded at the speed of a 1994 modem.

Then the interesting part. **The records are in Epson's own format** — not FIT, not GPX, not anything documented.

The obvious move is to reverse the format. I did something lazier and much better: I extracted Epson's own decoder — a native ARM64 library from inside their Android app — and ran it on my Linux laptop under a CPU emulator. No phone, no Android, no JVM. Their decoder, my machine.

That decision is worth stating plainly as a technique, because it generalises:

> When a format is undocumented but a decoder for it exists, running the decoder is often cheaper and *always* more correct than reimplementing it. And more importantly: it gives you an **oracle** — a source of ground truth to check everything else against.

That oracle is what caught bug number four. Hold that thought.

## Failure 1: the header that was four bytes longer than I thought

The download worked. Twenty-three records came off the watch, no errors, no timeouts, no short reads. Every file arrived.

Every file was also corrupt.

The response to each chunk request has a header, and I read that header as 10 bytes. It is 14 — status, class, element, index, then a **32-bit offset and a 32-bit length**. I had accounted for the offset and not the length. So four bytes of length field stayed inside the payload, once per chunk, every 900 bytes, all the way through every file.

What made it visible was not an error. It was arithmetic: the files were 83,588 bytes against a declared size of 83,584. Four bytes too long, in a 2 MB download, on a transfer that reported complete success.

Once you look with that hint, the corruption is obvious — `84 03 00 00` repeating at a fixed stride, which is just `900` in little-endian, written into the data every 904 bytes. Without the size comparison it is indistinguishable from binary noise in a format you do not yet understand.

**The lesson is cheap and general: if your source declares a size, compare it.** Not because you expect a mismatch, but because a length check is nearly free and it is one of the very few things that can catch a transport bug from the outside. Byte counts are a checksum you already have.

## Failure 2: the one where every latitude was zero

With the container assembled correctly, the decoder ran. It returned success. It returned 3,325 samples, 6 laps, 1,146 GPS points. Elapsed time counted up correctly. Direction, speed and cumulative distance were all present and all sensible.

Every latitude was `0`. Every longitude was `-2147483648` — `INT_MIN`, the format's marker for "no fix".

That is a completely coherent story. It says: *this watch recorded an activity but never acquired GPS.* An indoor run. A treadmill session. A watch that could not see the sky. I ran all 23 records and got the same answer 23 times, which reads as *this person always runs indoors* — unusual, but not impossible, and the data was internally consistent with it.

The cause was mine. To run a native library under emulation you must supply the C library functions it calls, and I had stubbed the maths functions — `sqrt`, `sin`, `cos`, `atan2` — to return `0`. Placeholders I wrote early, when I only wanted to see whether the thing would execute at all, and then forgot.

Geodesy is nothing but those four functions. Everything else in the decoder is integer bookkeeping and came out perfect. The stubs zeroed exactly one thing: position.

Wiring in real maths produced `43.749812, -79.206021`. Scarborough, Ontario. Nine and a half kilometres.

This is the failure I would put on a poster:

> **A wrong dependency produced a complete, self-consistent, plausible dataset with one channel silently zeroed.** No error. No warning. No missing rows. Just a story that happened to be false.

Note what would *not* have caught it. Not a schema — the field was present and correctly typed. Not a null check — the values were not null, they were `0` and `INT_MIN`. Not row counts, not a smoke test, not "did the job succeed". The only thing that catches this is knowing what the data is supposed to *mean* and noticing that the answer, while coherent, is not credible.

## Failure 3: the channel that was never there

I then wrote in my own documentation, as a statement of fact, that this watch has no optical heart-rate sensor.

I had evidence. The decoder returned no heart rate on any of the 23 activities. The output structure had no heart-rate array in it. The activities rendered fine without it. The absence was consistent, total, and explainable — plenty of older running watches use a chest strap and have no wrist sensor.

The watch has an optical sensor. The owner told me so.

The bug: the decoder's output has around twenty container fields, and every single one of them is a `{count, pointer}` pair — a length and an array. So I read them all that way. One is not. The distance container has **four** fields, not two:

```
+0x00  uint32  number of distance samples
+0x08  pointer to distance samples
+0x10  uint32  number of heart-rate samples     <- never read
+0x18  pointer to heart-rate samples            <- never read
```

I read the first pair and stopped. The distance samples came back completely correct, because they *are* the first pair. Nothing was malformed. Nothing was missing from the part I looked at. The heart rate was sitting in memory, fully decoded, at an offset I never visited.

Reading it gave 23 activities with heart rate on every one.

This is the worst of the four, and it is worth being precise about why:

> **Absent data is invisible to every check that operates on the data you have.** A validation suite examines rows that exist. It cannot flag a column you never selected. There is no anomaly to detect, no distribution to look wrong, no null to count — the pipeline is internally perfect and simply smaller than reality.

The generalisation is uncomfortable: *your pipeline cannot tell you what it is not reading.* Only something outside it can — a spec, an independent extract, a row count from the source system, or a human who knows the equipment. In this case it was a human, and I had already written my mistaken inference into two READMEs and a commit message as though it were a hardware fact.

Which brings up the meta-lesson. I did not just miss the data. I **explained** the absence, plausibly, and promoted my explanation to documentation. An unexplained gap invites investigation. A well-explained gap closes the ticket. Be most suspicious of the missing things you have a good story for.

## Failure 4: the label I invented

Once heart rate was in, I generated the activity files. Each one needs an activity type, and this is a running watch, so I set them all to `running`.

The most recent activity was 16 km in 45:56. That is 2:52 per kilometre — about 21 km/h, which is roughly world-record marathon pace, sustained for 16 km, by a hobbyist.

Now, the honest possibility here is that the *distance* was wrong. So I checked it against something that had not been through the same code path: I took the GPS track — a list of latitude/longitude fixes — and computed its length with the haversine formula. Two independent measurements of the same quantity, one from the device's accelerometer-and-GPS fusion, one from raw geometry.

They agreed to **0.7%**. On another activity, 1.4%.

So the distance is right, the pace is right, and it is simply not a run. It is a bike ride. The record format carries no activity type at all — I checked, and the metadata is byte-identical across all 23 records with nothing in the header behaving like an enum.

`running` was not data. It was my assumption, written into the output in a field that looks exactly like data to everyone downstream.

The fix was to label them `unknown`, which is less useful and more true. And it is the case that most of them *are* runs. But a store where 22 rows are right and one is a confident lie is worse than one that admits it does not know, because nothing downstream can distinguish them.

> Any field your pipeline **fills in** rather than **reads** is a claim you are making on the source's behalf. If it is not in the source, it does not get to look like it is.

While I was at it, the same cross-check settled a units question. Cadence: was the raw value steps per minute, or steps per minute per foot (i.e. double)? The laps carry their own step counts, so — 6,799 steps across the 2,822 samples that report a cadence is 144.6 steps per minute, against the channel's own average of 144. Not halved. Two independent paths to one number, agreeing to 0.4%.

## The fifth one, in different code

I then ported the parsers to JavaScript for a browser tool, and wrote a test that generates a FIT, a TCX and a GPX file, reads all three back, and checks them against each other.

GPX came back with no heart rate. FIT and TCX were fine.

GPX stores heart rate in a namespaced extension element, `<gpxtpx:hr>`. My code matched elements by local name, using the DOM's `localName` property, which in a conforming XML parser is prefix-free. It is not universally so. Where it was not, `gpxtpx:hr` stopped matching `hr` — and *only* the namespaced fields vanished. Latitude, longitude, elevation and time all parsed perfectly, because none of them are namespaced.

One format, one class of field, silently absent. Exactly the same shape as failure 3, in a completely different language and codebase, two days later.

A single-format test would have passed. The cross-format comparison caught it in one run, because it asked a question no single parser can answer about itself: *do independent readings of the same activity agree?*

## What actually catches this class of bug

Four failures, four different mechanisms — a transport off-by-four, a stubbed dependency, a struct misread, an invented label. What caught them has more in common than what caused them:

| Failure | Not caught by | Caught by |
|---|---|---|
| Corrupt chunks | success codes, no short reads | **byte count vs declared size** |
| Latitudes zeroed | schema, nulls, row counts | **domain plausibility** — a GPS watch with no fixes, ever |
| Heart rate absent | any check over the returned data | **an external fact** — the owner knew the hardware |
| Sport invented | nothing internal; it was self-consistent | **an independent measure** — GPS track length vs device distance |
| GPX fields absent | that parser's own tests | **cross-format agreement** |

![The same five failures as a figure. On the left, what each failure was, all of them reporting success. In the middle, the checks that could not see it — success codes, schema and null checks, the returned data itself, internal consistency, a parser's own tests. On the right, what did catch it, and in every case it is a second measurement of the same quantity arrived at by a different route: byte count against declared size, domain plausibility, an external fact, an independent measure, and cross-format agreement.](every-stage-reported-success/article_figure.webp)

Every one of them is a measurement taken by a *different route* than the one that produced the value. That is the only property they share, and I think it is the whole trick.

The practical version:

1. **Compare declared to actual.** Sizes, row counts, checksums. Free, and catches transport bugs from outside.
2. **Compute at least one important number two ways.** Distance from geometry as well as from the device. Cadence from steps as well as from the cadence channel. Agreement to a few percent is worth more than any amount of internal consistency.
3. **Treat a clean absence as a finding, not a fact.** Especially when you have a good explanation for it.
4. **Keep filled-in fields distinguishable from read fields.** `unknown` beats a plausible guess.
5. **If a decoder for your format exists, run it.** It is an oracle, and oracles are how you check the thing you wrote.

None of this is exotic. All of it is the kind of check that gets cut because the pipeline already works.

## The bonus

The viewer came out of this as a small standalone thing, and it is now public:

**https://doytsujin.github.io/ok-prosense-web/**

Drop a FIT, TCX or GPX file and it renders the route, pace, heart rate, elevation and splits. It is a static page — your file is parsed by JavaScript in your own tab, and there is no upload, no backend, no account and no build step. Map tiles default to *off*, because fetching a basemap sends tile coordinates to a third party, and that would quietly undercut the one promise the page makes. It reads any watch's export, not just the Epson one.

None of my own activities are in that repository, which left it with nothing to demonstrate on, so the README now points at public test files instead: Garmin's own FIT fixtures, real dumps off an Edge 500 and a fēnix, TCX from a tagged set of sport activities, and a spread of GPX. Two of them are listed because they are broken in useful ways. One GPX is written as eight separate `<trk>` elements, which reads as an empty file to anything that takes only the first track. Another has every timestamp set to the 1901 sentinel, and the page reports that as a route with no duration rather than as a confident 0:00 over 2.7 km — the same class of lie as the zeroed latitudes above, caught the same way.

Its own test page is the part I would reuse. It generates a FIT, a TCX, a GPX and a JSON file in the browser, reads all four back, and asserts they agree — 33 assertions, no fixtures on disk, and exactly the cross-check that caught the namespace bug above. No single-format test can perform it.

The watch-specific half — the Bluetooth protocol and the emulated decoder — stays in a CLI, because decoding those records requires Epson's own library and that is not mine to redistribute.

## The part that stays with me

I got the hard things right. The Bluetooth protocol, the packet framing, the flow control, running a foreign CPU architecture's binary under emulation and calling into it with the correct ABI — all of that worked, and none of it is where I lost time.

I lost time on four bugs that all had the same signature: **the pipeline said it was fine, and it was not**, and the output was plausible enough that I believed it and started writing it down as fact.

The tooling we have is very good at telling us that a job finished. It is almost silent on whether the result is true. That gap does not close with better error handling. It closes with the discipline of measuring the same thing twice, by different means, and caring when the two answers disagree.

---

*Written up from a real recovery job: 23 activities, 214.6 km, 2021 to 2026, off a watch whose cloud service shut down last year. The viewer is linked above; the files to try it on are listed in its README.*

---

<small>© 2026 Alexander Chernov. All rights reserved. First published on [LinkedIn](https://www.linkedin.com/pulse/every-stage-reported-success-data-wrong-alexander-chernov-yablc/), which remains the canonical version; this page is a reprint by the author.</small>
