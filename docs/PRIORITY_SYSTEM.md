# IndieQA error priority system

The dashboard preserves the detector's `severity` and adds a repair priority. The
priority is a triage recommendation for a developer; it does not change the bug
report or claim that every occurrence has a unique root cause.

| Priority | Detector severity | Meaning | Dashboard action |
|---|---|---|---|
| **P0** | `CRITICAL` | The player can cross solid geometry or escape the intended level. | Release blocker: inspect before shipping. |
| **P1** | `HIGH` | Progress can become impossible without a restart or recovery. | Fix before release. |
| **P2** | `MEDIUM` | A player-visible defect needs scheduled investigation. | Plan for the next development cycle. |
| **P3** | `LOW` | Impact is currently unclear or cosmetic. | Review after higher-priority work. |

Current planted-bug mappings are Wall Clip → P0, Infinite Fall → P1, Softlock →
P1, and Out of Bounds → P0. The dashboard exposes filters for severity, bug type,
and priority, then sorts the fix queue by priority and trigger frame.

## Visual evidence

The dashboard reconstructs an approach frame and detection frame from telemetry and
the real level geometry. It labels the image as a reconstruction so it is not
mistaken for a captured game screenshot. The generated pitch assets are:

- [`overview.png`](../data/evidence/overview.png)
- [`wall_clip.png`](../data/evidence/wall_clip.png)
- [`infinite_fall.png`](../data/evidence/infinite_fall.png)
- [`softlock.png`](../data/evidence/softlock.png)
