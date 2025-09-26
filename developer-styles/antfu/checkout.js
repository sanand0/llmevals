const graph = {
  idle: { NEXT: 'cart' },
  cart: { NEXT: 'address', BACK: 'idle' },
  address: { NEXT: 'payment', BACK: 'cart' },
  payment: { NEXT: 'done', BACK: 'address', FAIL: 'address' },
  done: { BACK: 'payment' },
};
export function createCheckoutMachine(initial = 'idle') {
  let current = graph[initial] ? initial : 'idle';
  const subs = new Set();
  const notify = () => subs.forEach(fn => fn(current));
  const allowed = () => Object.keys(graph[current] || {});
  const send = event => {
    const next = graph[current]?.[event];
    if (!next || next === current) return;
    current = next;
    notify();
  };
  const subscribe = fn => {
    subs.add(fn);
    fn(current);
    return () => subs.delete(fn);
  };
  return { get state() { return current }, send, allowed, subscribe };
}
