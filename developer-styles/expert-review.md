# Bring a panel of experts to review code

Bringing a panel of experts in to review or refactor a code base is increasingly realistic.

Here's what I asked [Codex CLI](https://developers.openai.com/codex/cli/) (`gpt-5-high`) on my [AIPipe](https://github.com/sanand0/aipipe/tree/074496275e4f39cfd8d9fc1205c1699fe0bc8b47) repo:

## user_message

Which of these developers would I bring in to rewrite this repo and why them?

| GitHub        | Name               | Style                                                                                                                                             |
| ------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| mbostock      | Mike Bostock       | low-level primitives and _explicit_ data>element bindings (d3); clean diffs; example-driven; notebook-native workflows.                           |
| sindresorhus  | Sindre Sorhus      | "tiny, sharp utilities". Minimal surface area, strong defaults, predictable names (`execa`, `ky`, `p-queue`, `globby`).                           |
| lukeed        | Luke Edwards       | "micro-libs, no fluff". Single-purpose modules; native ESM; minimal deps; straight-line code.                                                     |
| rich-harris   | Rich Harris        | "compiler-as-framework". Write components; the compiler outputs minimal runtime. Emphasis on DX + shipping less JS.                               |
| tannerlinsley | Tanner Linsley     | "headless, type-safe primitives". Framework-agnostic cores + typed adapters; declarative APIs (Query/Router/Table) with strong devtools.          |
| kentcdodds    | Kent C. Dodds      | "user-centric testing". Avoid implementation details; integration-first tests; pragmatic full-stack co-location patterns.                         |
| addyosmani    | Addy Osmani        | "performance patterns as first-class code". Ship less JS; progressive bootstrapping; pattern catalogs (patterns.dev) usable across stacks.        |
| evanw         | Evan Wallace       | "tooling as leverage". Single binary; clear CLI/JS APIs; fast defaults over heavy config.                                                         |
| davidkpiano   | David Khourshid    | "formal, visual state". Event-first, finite machines, visual tools; framework-agnostic.                                                           |
| antfu         | Anthony Fu         | "unplugin-everything; DX-first". Convention over config, on-demand utilities, editor-centric workflows.                                           |
| paulirish     | Paul Irish         | "performance-first, tooling-led frontend". Begin with a best-practice baseline, then _measure_ and iterate; progressive enhancement, diagnostics. |
| sebmck        | Sebastian McKenzie | "language-aware tooling". Compiler-grade transforms; cohesive DX across parse/lint/format.                                                        |
| jarred-sumner | Jarred Sumner      | "integrated runtime thinking". Batteries-included; prioritize startup/memory; pragmatic Node compat.                                              |
| developit     | Matteo Collina     | "measure first; zero-overhead Node". Schema-driven, plugin-centric, perf-budgeted code; tight JSON/HTTP control.                                  |
| developit     | Jason Miller       | "small framework thinking". 3kB-class frameworks, compile-free JSX (`htm`), pragmatic trade-offs.                                                 |
| ryansolid     | Ryan Carniato      | "fine-grained reactivity". Minimal abstractions around signals; control over reactivity graph; JSX without VDOM.                                  |

## agent_message

I’ll quickly scan the repo to understand its stack, goals, and pain points before recommending a fit.

## agent_message

Recommendation: Tanner Linsley

Why him

- Headless, type-safe primitives match this repo’s core: a provider-agnostic LLM proxy with budgets and usage. He’d turn today’s implicit contracts into a typed core with adapters, keeping runtime-agnostic and portable.
- Clear, declarative APIs and great devtools. Expect a small “AIPipe Core” with typed provider adapters (OpenAI/OpenRouter/Gemini), a pluggable cost engine, and DX tools to inspect requests/usage and SSE flows.
- Minimal surface area, strong defaults. The current entry points (`src/worker.js:1`, `src/providers.js:1`, `src/cost.js:1`) become thin wrappers around a stable core API that’s easy to extend and test.

What the rewrite would look like

- Core domain model in TypeScript: Token, Budget, UsageWindow, Provider, CostPolicy, SSEEvent.
- Adapters: `cloudflare-worker` (current), plus `node`, `bun`, `deno` as optional packages.
- Providers: strongly-typed adapters with shared cost calculators and usage parsers; tests are integration-first and avoid implementation details.
- Devtools: a lightweight panel/CLI to visualize per-request cost, budget windows, and SSE token counts in realtime.
- Keep the site frontend tiny and compile-free; move logic into the headless core.

If your goals differ

- Single-binary, anywhere deployment → Evan Wallace. He’d ship a blazing-fast CLI/proxy with a small config, great streaming defaults, and no heavy config.
- Ultra-small, zero-fluff modules → Luke Edwards. He’d decompose headers/SSE/JWT/cost into micro-libs and keep the worker a straight-line composition.
- DX plugins across ecosystems → Anthony Fu. He’d “unplugin” the provider/adapters and make editor-centric workflows first-class.

Why not others (for a full rewrite)

- Rich Harris, Ryan Carniato, Mike Bostock, David Khourshid are fantastic, but their strengths (compiler-driven UI, fine-grained reactivity, data binding, formal statecharts) don’t sit at the repo’s core.
- Addy Osmani, Paul Irish are perfect for performance audits and baseline tooling, less for a ground-up proxy-core redesign.
- Sebastian McKenzie, Jarred Sumner excel at language/runtime layers; here that’d be overkill versus a typed, headless proxy/core.

Short answer: pick Tanner to turn AIPipe into a clean, typed, provider-agnostic core with adapters and great devtools, while keeping the runtime and UI minimal.

## user_message

How would Luke Edwards rewrite this?

## agent_message

Here’s how Luke Edwards would likely tackle a rewrite: split into tiny, focused ESM modules with straight-line code, zero fluff, and minimal runtime branching. Keep the worker thin; push logic into micro-libs you can reuse in Node/Deno/Edge.

**Principles**

- Micro-libs over frameworks: single-purpose files, tiny exports, no global state.
- Native ESM, sideEffects: false, no build step for runtime code.
- Straight-line handlers: fast path first, minimal branches, explicit returns.
- Adapter-first: core is runtime-agnostic; adapters wire it to Cloudflare/Node.

**Package Layout**

- `@aipipe/core`: routing, auth, provider dispatch, cost accounting.
- `@aipipe/headers`: `update(headers, skip, next)`, `cors(req)`.
- `@aipipe/sse`: zero-dep SSE passthrough with incremental JSON capture.
- `@aipipe/auth-jwt`: tiny HS256 JWT sign/verify via WebCrypto or worktop/jwt.
- `@aipipe/cost`: pure functions for token→$ calc; static price tables per provider.
- `@aipipe/store`: storage interface + adapters: memory, CF DO, D1/SQLite.
- `@aipipe/providers/*`: `openrouter`, `openai`, `geminiv1beta`—each a 50–150 line module.
- `@aipipe/adapter-cloudflare`: `fetch(req, env)` that calls core.
- `examples/*`: `cloudflare-worker`, `node-http`, `deno`.

**Core APIs**

- `createRouter({ providers, store, budget, salt })` returns `{ handle(req, env) }`.
- `createProvider({ transform, parse, cost })` consistent shape for all providers.
- `createStore(storeLike)` expects `{ add(email,c), sum(email, from,to), set(email,date,c), all() }`.
- `auth.verify(token, secret, saltMap)` returns `{ email } | { error }`.

**Request Flow**

- Parse path first, no heavy router. Tiny `regexparam`-style matching.
- Special-cases early: OPTIONS, `/proxy/*`, `/token`, `/usage`, `/admin/*`.
- Auth once; hoist email/domain; compute `{limit,days}` inline from config.
- Provider dispatch: call `transform()`, forward fetch, stream passthrough, `parse()` for usage hints.
- Cost add occurs in two places:
  - JSON body once (clone only when `content-type` is JSON).
  - SSE via `@aipipe/sse` flush hook capturing last `{model, usage}`.

**Storage**

- Interface-first: memory store default for tests; Cloudflare Durable Object as an adapter.
- CF DO adapter mirrors current behavior from `src/cost.js:1`, but the core never imports CF types.
- Optionally include a D1 adapter for daily rows.

**Providers**

- OpenAI/OpenRouter/Gemini each live in their own file (no shared mutable state).
- All cost logic is pure per-provider, reading static price tables.
- OpenRouter model pricing lookup is lazy with a TTL cache; never in hot path when `usage` exists.

**Auth**

- Replace `jose` with a tiny HS256 module over WebCrypto or `worktop/jwt` for Workers.
- Functions: `sign(payload, secret)`, `verify(token, secret)`. Salt check is a single branch.

**SSE**

- A 40–60 line module:
  - Reassemble lines with a buffer; only parse lines starting with `data: `.
  - Track first-seen `model` and latest `usage`; call `onFlush({model,usage})`.
  - Passthrough chunks unmodified.

**Tooling & Tests**

- Tests use `uvu` per package; memory store for unit, tiny in-process fetch for integration.
- No dev server dependency; Cloudflare example uses wrangler only in the example.
- Coverage via `c8`. Benchmarks optional, simple Node scripts.

**Example Entrypoint (Cloudflare)**

- `@aipipe/adapter-cloudflare`:
  - `export default { fetch: (req, env) => router.handle(req, env) }`
  - No side effects, no global caches outside `env` scope.

**Mapping From Current Repo**

- `src/worker.js:1` → `@aipipe/adapter-cloudflare` (fetch) + `@aipipe/core` (handle).
- `src/providers.js:1` → `@aipipe/providers/*` + `@aipipe/sse` + `@aipipe/cost`.
- `src/cost.js:1` → `@aipipe/store/cf-do` adapter; interface lives in `@aipipe/store`.
- `src/utils.js:1` → `@aipipe/headers` + `@aipipe/auth-jwt` + `@aipipe/dates` (ymd).
- Keep `public/*` static and minimal; move logic out of pages into core/HTTP.

**Migration Steps**

- Extract headers/auth/dates into micro-libs; swap imports in `worker`.
- Split providers; keep signatures (`transform`, `parse`, `cost`) unchanged.
- Introduce `store` interface and shim current Durable Object.
- Replace SSE logic with a tiny stream module.
- Move tests to module-level uvu suites; keep current endpoint semantics identical.

This yields a tiny, fast, portable codebase: small files you can read in one screen, minimal deps, straight-line handlers, and adapters that make the same core run on Workers, Node, or Deno without ceremony.

## user_message

Whose style would best align with the repo as-is?

## agent_message

Luke Edwards, with Sindre Sorhus as a close runner‑up.

Why Luke Edwards aligns best

- Native ESM and minimal deps: repo ships zero build and only `jose` as a dep (`package.json:1`), matching “micro-libs, no fluff.”
- Straight-line code paths: request flow is explicit and branch-light in `src/worker.js:1`; helpers are tiny and single-purpose in `src/utils.js:1`.
- Small, composable modules: providers are plain objects with `transform/parse/cost` (`src/providers.js:1`), SSE is a focused 60‑ish line transform, and the Durable Object is a concise store (`src/cost.js:1`).
- Runtime-agnostic patterns: logic is mostly platform-neutral JS, with the Workers adapter kept thin—exactly the “micro-libs + thin adapters” vibe.

Why Sindre Sorhus is runner-up

- “Tiny, sharp utilities” shows up in helpers like `updateHeaders`, `addCors`, `ymd` (`src/utils.js:1`) and predictable names across providers. The repo, though, is an app/proxy more than a utilities toolkit, so Luke’s micro‑lib, adapter mindset is a tighter fit.

Why not others for “as-is” alignment

- Rich Harris, Ryan Carniato: compiler/reactivity-heavy UI focus; this repo is headless/edge-first.
- Tanner Linsley: great for a typed, headless core with adapters (a future rewrite), but current code is untyped JS.
- Evan Wallace, Sebastian McKenzie, Jarred Sumner: tooling/runtime centric; overkill for this lean Worker.
- Addy Osmani, Paul Irish: perf/process excellence; less about the current code’s style.
- Mike Bostock, David Khourshid: data-binding/statecharts paradigms don’t surface here.

## user_message

How would Luke Edwards rewrite this repo if we wanted fewer files and larger files were OK?

## agent_message

Here’s a Luke-Edwards-style rewrite with fewer, larger files: collapse to a single straight-line Worker (plus static assets), keep zero fluff, and minimize deps. It preserves current behavior, just tighter and flatter.

**File Layout**

- `src/worker.js` only: includes router, auth, CORS/headers, SSE, providers, pricing tables, and Durable Object.
- `public/*` unchanged.
- Optional: keep `src/pricing.json` if you prefer not to inline the tables; everything else merges.

**Single-File Structure (sections in order)**

- Constants: skip-header patterns, small helpers, inlined pricing tables or `import pricing`.
- Auth (tiny HS256): `sign(payload, secret)` and `verify(token, secret)` via WebCrypto. Keep `jose` only for Google credential verification, but lazy-load it inside `/token` path so it never hits the hot path.
- CORS/Headers: `updateHeaders`, `addCors`, `ymd` inlined; pure and tiny.
- SSE Transform: 40–60 lines. Buffer lines, parse only `data:` JSON, keep first `model` and last `usage`, call `onFlush` once, pass chunks through.
- Providers object: `openrouter`, `openai`, `geminiv1beta`, `similarity` each as small inline objects with `{ transform, parse, cost }`. Keep OpenRouter model cache with a simple TTL local variable.
- Store (Durable Object): `class AIPipeCost` unchanged but in this file; same SQL schema and methods.
- Router: a single `fetch(request, env)` with early returns for `OPTIONS`, `/proxy/*`, `/token`, `/admin/*`, `/usage`, else provider dispatch. Straight-line, minimal branches.

**Key Changes vs Current**

- Collapse `src/providers.js`, `src/cost.js`, `src/utils.js` into `src/worker.js:1`. The providers and SSE code from `src/providers.js:1` lift verbatim with minor refactors for local references.
- Keep `AIPipeCost` class exactly as in `src/cost.js:1`, just moved; `wrangler.toml` already points `class_name = "AIPipeCost"`, which can live in the main module.
- Replace `jose` for signing/verifying our HS256 JWT with a tiny WebCrypto helper; dynamically `import('jose')` only inside `/token` for Google JWKS verification. This preserves correctness with minimal cold-start cost.
- Keep config inline: a small `const budget` and `const salt` near the top (you can still generate production tokens via `/admin/token`).
- Keep behavior identical: same endpoints, headers, status codes, and cost accounting.

**Tiny HS256 Auth (WebCrypto)**

- Straightforward and tiny; used for our tokens only.
- Example shape (inside the file, no external deps):
  - `async function hmacKey(secret) { return crypto.subtle.importKey('raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign','verify']); }`
  - `async function signHS256(payload, secret) { /* base64url(header).base64url(payload).base64url(sig) */ }`
  - `async function verifyHS256(token, secret) { /* split/verify+JSON.parse */ }`

**Router Flow (straight-line)**

- If `OPTIONS` → return CORS with `Access-Control-Max-Age: 86400`.
- Parse `provider` from path; handle `/proxy/*`, `/token`, `/usage`, `/admin/*` early.
- Require token for all provider routes; `verifyHS256` + salt check.
- Domain/user budget from inline config; compute window; deny at 429 if exceeded.
- Provider dispatch:
  - `const { url, headers, error, ...params } = await providers[p].transform({ path, request, env })`
  - `fetch(url, { method, headers: updateHeaders(...), ...params })`
  - If JSON → `await addCost(parsed)`. If SSE → pipe through `sseTransform(provider, addCost)`.
- Respond with updated headers via `addCors(updateHeaders(...))`.

**Providers (inline)**

- `openrouter`: lazy model list cache for pricing; compute cost when `usage` present or derived.
- `openai`: cost via token table; ensure chat stream sets `stream_options.include_usage`.
- `geminiv1beta`: rewrite to `x-goog-api-key`, try `:countTokens` when needed.
- `similarity`: keep as-is; single POST handler that calls OpenAI embeddings then computes cosine sims.

**Migration Plan**

- Move `AIPipeCost` from `src/cost.js:1` into `src/worker.js` unchanged.
- Paste `updateHeaders`, `addCors`, `ymd`, and `createToken` into the top of `src/worker.js`; replace `createToken` to use the new HS256 signer.
- Inline or import `pricing` at the top; update provider cost lookups to reference local tables.
- Inline `sseTransform` and `providers` into `src/worker.js`.
- Replace `jose` usage for our JWT with the HS256 helpers; keep `jose` dynamic import inside `/token` only.
- Remove now-unused `src/*` files and update imports. `wrangler.toml` remains the same.

**Trade-offs**

- Pros: fewer files, fewer imports, faster read/understand cycle, less indirection, minimal deps on hot path.
- Cons: larger file requires discipline with clear sectioning and small pure functions; unit testing moves to integration-style tests or sectioned test helpers.

Net: You get a single, direct, dependency-light Worker that mirrors Luke’s “micro-libs, no fluff” ethos—consolidated into one readable file with straight-line control flow and zero unnecessary abstractions.

---

**Why use a generic coding agent when it can write in an expert's style?**
