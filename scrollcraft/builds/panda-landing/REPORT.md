# PandaSet landing delivery

Built in the separate `codex/panda-landing` worktree. Creative brief self-authored under the user's explicit delegation. Development: http://127.0.0.1:45273/; reviewed production bundle: http://127.0.0.1:45274/.

## Experience

**Grammar:** companion field guide. An in-flow masthead, layered mascot introduction, compact recognition passage, one operable comparison, an indexed toolkit, and a final invitation. The default grammars and why each lost are recorded in BRIEF.md. This structure lets the panda support a real product explanation without turning the whole page into a dashboard or a video.

**Signature and peak:** Panda's perspective. Two eye-shaped selectors compare the same sample's capital allocation and risk contribution. Desktop scroll reveals the risk view; manual selection takes precedence. Touch and reduced-motion visitors control the comparison directly. The black comparison section is the longest section and follows the quiet recognition passage.

**Journey:** meet Panda → recognize the gap between owning and understanding → uncover risk → discover the four workflows → enter the demo.

| Beat         | Device                              | Intended feeling | Final visual reading             |
| ------------ | ----------------------------------- | ---------------- | -------------------------------- |
| Introduction | Independent parallax planes         | Curiosity        | Curiosity                        |
| Recognition  | Kinetic sentence in natural flow    | Recognition      | Recognition after spacing repair |
| Comparison   | Short pin plus custom eye selectors | Discovery        | Discovery                        |
| Toolkit      | Whole-list reveal                   | Confidence       | Confidence                       |
| Invitation   | Stable natural flow                 | Readiness        | Readiness                        |

First visual pass: the recognition sentence lost the space at its line break after the engine split its words. It read as a run-on phrase and interrupted the intended calm pause. Explicit whitespace repairs the sentence. The large dark comparison provides the intended peak, and the final invitation remains visible at the bottom. No authored empty screens.

**Fingerprint gate:** the registry was empty, so there were no previous rows to compare. This build records all six dimensions for future comparisons.

## Assets and integration

Original full-body SVG extends the existing PandaMark; the landing has its own monochrome favicon. Existing self-hosted DM Sans is reused. No photos, raster generation, video, external fonts, or paid asset requests. Kie.ai was not configured and was not needed for the vector artwork.

The scrollcraft engine and stylesheet were copied unchanged into this build folder. React renders semantic markup; the engine drives that markup. The landing is a separate Vite entry at index.html, so dashboard styling and the engine lifecycle cannot leak into each other. The existing app lives at app.html with its existing hash routes. Previously shared root dashboard hashes redirect while preserving query parameters.

All chart values come from the existing TypeScript analytics and sample weights. Signed risk bars preserve negative contributions. The illustrative data label and variance explanation stay beside the chart. The dashboard's backend workflow is unchanged.

## Verification

- `npm test`: all 19 existing tests passed.
- `npm run build`: TypeScript and both production entry points passed.
- Prettier checks and `git diff --check` passed for changed frontend files.
- Production screenshots inspected at 1440 × 900, 390 × 844, and reduced motion; functional screenshots also inspected at 360 × 640.
- Final scroll harness: 25 positions each for desktop, phone, and reduced motion. No reported dead scroll, request failures, or console errors. Animated copy cleared the harness's measured contrast checks. This check is specific to cue text, not an assertion that the harness audited every element.
- Functional browser checks: no horizontal overflow; keyboard skip link and focus order; mobile menu open/close and Escape; both perspective controls; signed negative risk bar; automatic desktop scroll transition; workflow destinations; closing action; all four legacy dashboard hashes; dashboard API error and retry state with an intercepted 503.
- The initial error-state test intercepted a development source file under `/src/api/` as well as actual API calls. Restricting interception to the `/api/` pathname fixed the test; no product change was needed.
- First chart review identified an absolute-value bar for a negative risk contribution. Final code preserves the sign and includes a zero baseline and explanatory note. The signed-* screenshot runs supersede earlier chart runs; originals remain in the ignored local lab folder.

Screenshots and final machine reports are in `evidence/`. Full intermediate frames remain in ignored `lab/`. Reproduce interaction checks after `npm install --no-save --package-lock=false playwright-core` with `LANDING_URL=http://127.0.0.1:45274 node scrollcraft/builds/panda-landing/verify.mjs`. The script uses installed macOS Chrome; change its executable path on other systems.

Not verified: a physical phone or Safari, external hosting, or optional Gemini integration. No live-market or brokerage claim is made. No pointer-only interaction or video decoder is required.

## Motion refinement

Pandaset now has a finite hero arrival, a line chart that draws across the paper, pointer-driven panda gaze and head tilt, a brief blink on pointer entry, subtle paper perspective, progressive word emphasis while scrolling, staggered toolkit entrances, and a closing panda nod. The page keeps the companion field-guide grammar, existing journey, signature comparison, and peak span. This is a revision of the existing fingerprint, not a new build claiming structural uniqueness. No new assets or services were needed.

The choreography lives in `useLandingMotion.ts` and landing styles; the shared engine remains unchanged. Pointer effects require a fine mouse pointer. The new hook batches scroll/pointer writes through requestAnimationFrame, skips offscreen scene updates, removes its observers/listeners/timers on cleanup, and responds to live reduced-motion changes. No ambient effect loops indefinitely. Keyboard focus reveals toolkit links immediately, including the parent clip.

Verification of the final production bundle: all 19 tests, build, formatting, existing desktop/phone/compact/reduced functional checks, and three 25-frame scroll captures passed. The separate `verify-motion.mjs` confirms actual scene pixels change between pointer positions, chart arrival changes the rendered clip, gaze resets on exit, text resolves with scroll, keyboard links become visible, live reduced motion stops the custom choreography, touch does not activate pointer tracking, and no animations continue running after the finite arrivals finish. No page errors were recorded.

Visual review: curious → recognition → discovery → confidence → readiness. The new acknowledgement by Panda makes curiosity more personal, while the dark capital/risk section remains the peak. The first motion pass needed no layout repair. Word emphasis uses a visible 0.6 opacity floor and resolves fully before the sentence leaves. The cue-only contrast harness no longer measures that bespoke sentence; its appearance was inspected directly rather than treating the absence of cue warnings as a contrast audit.

Final motion screenshots and the interaction report are in `evidence/motion/`; these supersede the earlier static presentation evidence. Reproduce with `node scrollcraft/builds/panda-landing/verify-motion.mjs` against the production preview. Real-device Safari/iPhone testing remains unverified.


## Continuous scrolling correction

The black comparison now stays in native document flow. Removing its sticky stage and extra scroll span eliminates the stop and release at its boundaries. Its chart eases upward into place once, and Capital/Risk changes only through the selectors. This supersedes the earlier pinned comparison and automatic scroll selection described above. No wheel interception or simulated inertia was added; the contrast still gives this section its emphasis.

Verification: all 19 tests, production build, formatting, functional checks, and motion checks passed. The functional check now measures section movement across entry, middle, and exit and verifies that a manual perspective choice persists. Desktop, mobile, and reduced-motion captures each cover 25 scroll positions with no reported dead scroll or errors. All three contact sheets were visually inspected. Latest sheets replace `evidence/motion/*-scroll.png`; `evidence/native-scroll.json` records the updated functional checks. Physical-device Safari testing remains unverified.
