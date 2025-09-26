const flow = ["idle","cart","address","payment","done"];
const transitions = {
  NEXT: s => (s === "done" ? s : flow[flow.indexOf(s) + 1]),
  BACK: s => (s === "idle" ? s : flow[flow.indexOf(s) - 1]),
  FAIL: s => (s === "payment" ? "address" : s)
};
const allowedFor = s => { const events = []; if (s !== "done") events.push("NEXT"); if (s !== "idle") events.push("BACK"); if (s === "payment") events.push("FAIL"); return events; };
export function createCheckoutMachine(initial = "idle") {
  let state = flow.includes(initial) ? initial : "idle";
  const subs = new Set();
  const send = event => {
    const events = allowedFor(state);
    if (!events.includes(event)) return;
    const next = transitions[event](state);
    if (next === state) return;
    state = next;
    subs.forEach(fn => fn(state));
  };
  const subscribe = fn => {
    subs.add(fn);
    fn(state);
    return () => subs.delete(fn);
  };
  return { get state() { return state; }, send, allowed: () => allowedFor(state), subscribe };
}
