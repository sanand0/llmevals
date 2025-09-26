const flow = ["idle","cart","address","payment","done"];
const allowedEvents = { idle: ["NEXT"], cart: ["BACK","NEXT"], address: ["BACK","NEXT"], payment: ["BACK","NEXT","FAIL"], done: ["BACK"] };
export function createCheckoutMachine(initial = "idle") {
  let index = flow.indexOf(initial); if (index < 0) index = 0;
  let state = flow[index];
  const subs = new Set();
  const update = next => {
    if (next === index) return;
    index = next;
    state = flow[index];
    subs.forEach(f => f(state));
  };
  const send = event => {
    if (event === "NEXT" && state !== "done") update(index + 1);
    else if (event === "BACK" && state !== "idle") update(index - 1);
    else if (event === "FAIL" && state === "payment") update(flow.indexOf("address"));
  };
  const allowed = () => allowedEvents[state].slice();
  const subscribe = fn => {
    subs.add(fn);
    fn(state);
    return () => subs.delete(fn);
  };
  return {
    get state() { return state; },
    send,
    allowed,
    subscribe
  };
}
