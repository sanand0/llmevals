const steps = ["idle","cart","address","payment","done"];
export function createCheckoutMachine(initial = "idle") {
  let current = steps.includes(initial) ? initial : "idle";
  const subs = new Set();
  const notify = () => subs.forEach(fn => fn(current));
  const send = event => {
    let next = current;
    if (event === "NEXT" && current !== "done") next = steps[steps.indexOf(current) + 1];
    else if (event === "BACK" && current !== "idle") next = steps[steps.indexOf(current) - 1];
    else if (event === "FAIL" && current === "payment") next = "address";
    if (next !== current) { current = next; notify(); }
  };
  const allowed = () => {
    if (current === "idle") return ["NEXT"];
    if (current === "cart") return ["NEXT", "BACK"];
    if (current === "address") return ["NEXT", "BACK"];
    if (current === "payment") return ["NEXT", "BACK", "FAIL"];
    return ["BACK"];
  };
  const subscribe = fn => { subs.add(fn); fn(current); return () => subs.delete(fn); };
  return {
    get state() { return current; },
    send,
    allowed,
    subscribe
  };
}
