const flow = { idle: "cart", cart: "address", address: "payment", payment: "done" };
const trail = { cart: "idle", address: "cart", payment: "address", done: "payment" };
const options = { idle: ["NEXT"], cart: ["BACK", "NEXT"], address: ["BACK", "NEXT"], payment: ["BACK", "NEXT", "FAIL"], done: ["BACK"] };

export function createCheckoutMachine(initial = "idle") {
  let state = options[initial] ? initial : "idle";
  const subs = new Set();
  const inform = () => subs.forEach(fn => fn(state));
  const shift = next => { if (next && next !== state) { state = next; inform(); } };
  const send = event => {
    if (event === "NEXT") shift(flow[state]);
    else if (event === "BACK") shift(trail[state]);
    else if (event === "FAIL" && state === "payment") shift("address");
  };
  const allowed = () => options[state].slice();
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
