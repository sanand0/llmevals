const flow = ["idle","cart","address","payment","done"];
export function createCheckoutMachine(initial="idle") {
  let state = initial;
  const subs = new Set();
  const allowed = () => {
    const i = flow.indexOf(state), out = [];
    if (i < flow.length - 1) out.push("NEXT");
    if (i > 0) out.push("BACK");
    if (state === "payment") out.push("FAIL");
    return out;
  };
  const send = evt => {
    if (!allowed().includes(evt)) return;
    const i = flow.indexOf(state);
    state = evt === "NEXT" ? flow[i + 1] : evt === "BACK" ? flow[i - 1] : "address";
    subs.forEach(fn => fn(state));
  };
  return {
    get state() { return state; },
    send,
    allowed,
    subscribe(fn) {
      subs.add(fn);
      fn(state);
      return () => subs.delete(fn);
    }
  };
}
