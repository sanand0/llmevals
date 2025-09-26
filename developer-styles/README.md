# Mimicking Developer Styles with Coding Agents

LLMs mimic Studio Ghibli art. What if they mimic-ed developers? And solved a SINGLE problem in their styles? Can we learn from that?

I picked a [five-step checkout state machine problem](template.md):

- Create one JavaScript file ≤30 lines (no dependencies) that implements `createCheckoutMachine() → { state, send, allowed, subscribe }.`
- The checkout state goes from `idle → cart → address → payment → done`.
- `NEXT` moves the state forward. `BACK` moves backwards. `FAIL` on `payment` goes to `address`.

I had ChatGPT identify [famous JS developers](./developer-styles.tsv) and used [Codex CLI](https://github.com/openai/codex/) to [write code](./run.sh) in each developer's style (_"Write in the style of $DEVELOPER."_)

Here is the result:

| Developer                                         | How their code works                                                                                                                                                                                                                                                                                                                     |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [addyosmani](https://github.com/addyosmani)       | [Code](addyosmani/checkout.js) used a `transitions` "table" of functions to get the next value. He calls `allowedFor(state)` **before** computing `next` to validate. That's a clean separation of _can I?_ vs _do it_.                                                                                                                  |
| [antfu](https://github.com/antfu)                 | [Code](antfu/checkout.js) used a `graph` object that maps each state to its next states. He implements `allowed()` as `Object.keys(graph[current])` to list valid events for the current state. That keeps branching low and makes the code friendly to edit.                                                                            |
| [davidkpiano](https://github.com/davidkpiano)     | [Code](davidkpiano/checkout.js) used a small helper `shift(delta)` to move forward or back through the steps. He then dispatches via a `transitions` map of tiny functions. That reads like a compact, explicit state machine.                                                                                                           |
| [developit](https://github.com/developit)         | [Code](developit/checkout.js) wrote straight-line, imperative code with a tiny `move(next)` helper to change state. He hand-wrote the `allowed()` cases for clarity. It’s very easy to skim.                                                                                                                                             |
| [evanw](https://github.com/evanw)                 | [Code](evanw/checkout.js) returned a compact `api` object and used optional chaining on the `graph` lookups. He calls `notify(state)` with the new state, which leaves room to extend notifications later. It feels neat and tooling-like.                                                                                               |
| [jarred-sumner](https://github.com/jarred-sumner) | [Code](jarred-sumner/checkout.js) inlined almost everything for speed, but he **does not validate `initial`**. With an invalid initial state, a `BACK` event can set `state` to `undefined` (because `steps[index-1]` with `index=-1` becomes `undefined`) and then notify subscribers with `undefined`. It’s fast, but has sharp edges. |
| [kentcdodds](https://github.com/kentcdodds)       | [Code](kentcdodds/checkout.js) defined a clear `allowedMap`, plus small `move(next)` and `notify()` helpers. The surface area is gentle and test-friendly.                                                                                                                                                                               |
| [lukeed](https://github.com/lukeed)               | [Code](lukeed/checkout.js) kept a micro-library feel and first guards with `allowed().includes(evt)`. He **does not normalize `initial`**. That’s mostly safe: the first `NEXT` snaps to `'idle'`, while other events are blocked.                                                                                                       |
| [mbostock](https://github.com/mbostock)           | [Code](mbostock/checkout.js) based everything on an index and updates via `update(nextIndex)` and avoids re-looking up allowed events. He also kept separate `allowedEvents`. It’s very explicit, diff-friendly, and avoids recomputing work.                                                                                            |
| [paulirish](https://github.com/paulirish)         | [Code](paulirish/checkout.js) extracted a pure `nextState(state, event)` function. He also kept a **mutable** `machine.state` field in sync with the internal `state`. That matches the target TypeScript shape, but it’s a foot-gun: consumers can assign `machine.state = 'done'` and desync things.                                   |
| [rich-harris](https://github.com/rich-harris)     | [Code](rich-harris/checkout.js) wrote a direct, branchy `send` with a tidy `notify()` call. He listed `allowed()` explicitly per state. The result is clear and compiler-friendly, with no indirection.                                                                                                                                  |
| [ryansolid](https://github.com/ryansolid)         | [Code](ryansolid/checkout.js) used two maps—`flow` for forward and `trail` for back—so `NEXT`/`BACK` never need indices. He drives `allowed()` from an `options` map. It’s nicely decomposed.                                                                                                                                            |
| [sebmck](https://github.com/sebmck)               | [Code](sebmck/checkout.js) used a compiler-style `flow` graph and returned a single `api` object. He relied on optional chaining and key lookups. It’s cohesive and tersely “tooling”.                                                                                                                                                   |
| [sindresorhus](https://github.com/sindresorhus)   | [Code](sindresorhus/checkout.js) added tiny helpers (`STEPS`, `indexOf`) and gated with `allowed()` early to keep branching minimal. It feels like a sharp utility.                                                                                                                                                                      |
| [tannerlinsley](https://github.com/tannerlinsley) | [Code](tannerlinsley/checkout.js) paired an `allowedMap` with a `setState(next)` helper that both updates and notifies. That makes the internal API ergonomic.                                                                                                                                                                           |

Some **common patterns**:

- **Observer set.** All use a `Set` for subscribers and call each subscriber on change, **and once on subscribe**.
- **Read-only state (mostly)** via `get state(){...}` to prevent external mutation.
- **Input normalization (mostly)** of `initial` to ensure initial state is OK.

Some **differences**:

- Some developers use adjacency maps. Others use array indexing.
  - **Adjacency maps** are used by `antfu`, `evanw`, `sebmck` _(and close cousin `ryansolid`, who splits forward/back maps)_. E.g. `graph[state]?.[event]`, `allowed()` = `Object.keys(graph[state])`. Easier to add/branch events. Great for non-linear flows.
  - **Array indexing** is used by `addyosmani`, `davidkpiano`, `developit`, `rich-harris`, `sindresorhus`, `tannerlinsley`, `kentcdodds`, `mbostock`, `paulirish`, `lukeed`, `jarred-sumner`. E.g. `steps.indexOf(state)`; NEXT/BACK via `±1`. Minimal for linear flows. Fewer objects.
- Some developers **precompute the `allowed` map**, e.g. `mbostock`, `kentcdodds`, `tannerlinsley`, `paulirish`, `ryansolid`. A stable "allowed" policy makes testing and refactors safer.
- Some developers return **array copies** in `allowed()` to prevent consumers mutating the returned list. Subtle but solid API hygiene and a professional touch.
- Two developers, `jarred-sumner` and `lukeed`, skipped input state normalization. That means that:
  - `jarred-sumner`: a `BACK` event on an `initial` state ⇒ `undefined` state.
  - `lukeed`: an invalid `initial` ignores until `NEXT`, then snaps to `'idle'`. (Safer than Jarred’s).

By studying the masters, we learn a lot about how to approach a problem.

But with LLM style transfer, we _no longer need masters to learn from their work_. We can apply _all_ their methods to _any_ problem.

To me, that's staggering!
