const steps = ["idle","cart","address","payment","done"];
const allowedMap = {idle:["NEXT"],cart:["BACK","NEXT"],address:["BACK","NEXT"],payment:["BACK","NEXT","FAIL"],done:["BACK"]};
export function createCheckoutMachine(initial = "idle") {
  let state = steps.includes(initial) ? initial : "idle";
  const subs = new Set();
  const notify = () => subs.forEach(fn => fn(state));
  const setState = next => next && next !== state && ((state = next), notify());
  const send = e => {
    if (e === "NEXT") {
      const i = steps.indexOf(state);
      if (i > -1 && i < steps.length - 1) setState(steps[i + 1]);
    } else if (e === "BACK") {
      const i = steps.indexOf(state);
      if (i > 0) setState(steps[i - 1]);
    } else if (e === "FAIL" && state === "payment") {
      setState("address");
    }
  };
  const allowed = () => allowedMap[state].slice();
  const subscribe = fn => {
    subs.add(fn);
    fn(state);
    return () => subs.delete(fn);
  };
  return {get state(){return state;},send,allowed,subscribe};
}
