const flow = ["idle","cart","address","payment","done"];
const allowedMap = {
  idle: ["NEXT"],
  cart: ["NEXT","BACK"],
  address: ["NEXT","BACK"],
  payment: ["NEXT","BACK","FAIL"],
  done: ["BACK"],
};
export function createCheckoutMachine(initial = "idle") {
  let state = flow.includes(initial) ? initial : "idle";
  const listeners = new Set();
  const notify = () => listeners.forEach(listener => listener(state));
  const move = next => { if (state === next) return; state = next; notify(); };
  return {
    get state() { return state; },
    send(event) {
      const index = flow.indexOf(state);
      if (event === "NEXT" && index < flow.length - 1) move(flow[index + 1]);
      else if (event === "BACK" && index > 0) move(flow[index - 1]);
      else if (event === "FAIL" && state === "payment") move("address");
    },
    allowed() { return [...allowedMap[state]]; },
    subscribe(fn) {
      listeners.add(fn);
      fn(state);
      return () => listeners.delete(fn);
    },
  };
}
