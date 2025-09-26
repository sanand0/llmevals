const steps = ["idle","cart","address","payment","done"];
export function createCheckoutMachine(initial = "idle") {
  let state = initial;
  const subscribers = new Set();
  return {
    get state() { return state; },
    send(event) {
      let next = state, index = steps.indexOf(state);
      if (event === "NEXT" && state !== "done") next = steps[index + 1];
      else if (event === "BACK" && state !== "idle") next = steps[index - 1];
      else if (event === "FAIL" && state === "payment") next = "address";
      if (next !== state) {
        state = next;
        for (const fn of subscribers) fn(state);
      }
    },
    allowed() {
      const out = [];
      if (state !== "done") out.push("NEXT");
      if (state !== "idle") out.push("BACK");
      if (state === "payment") out.push("FAIL");
      return out;
    },
    subscribe(fn) {
      subscribers.add(fn);
      fn(state);
      return () => subscribers.delete(fn);
    }
  };
}
