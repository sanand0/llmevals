const flow = {
  idle: {NEXT: "cart"},
  cart: {NEXT: "address", BACK: "idle"},
  address: {NEXT: "payment", BACK: "cart"},
  payment: {NEXT: "done", BACK: "address", FAIL: "address"},
  done: {BACK: "payment"},
};

export function createCheckoutMachine(initial = "idle") {
  let state = initial in flow ? initial : "idle";
  const subs = new Set();
  const emit = () => subs.forEach(fn => fn(state));
  const api = {
    get state() { return state; },
    send(event) {
      const next = flow[state]?.[event];
      if (!next || next === state) return;
      state = next;
      emit();
    },
    allowed() {
      return Object.keys(flow[state] || {});
    },
    subscribe(fn) {
      subs.add(fn);
      fn(state);
      return () => subs.delete(fn);
    }
  };
  return api;
}
