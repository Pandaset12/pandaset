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
