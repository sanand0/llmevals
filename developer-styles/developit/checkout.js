const steps = ['idle','cart','address','payment','done'];
export function createCheckoutMachine(initial='idle'){
  let state = steps.includes(initial) ? initial : 'idle';
  const subs = new Set();
  const move = next => { if (state === next) return; state = next; subs.forEach(fn => fn(state)); };
  const send = event => {
    if (event === 'NEXT') {
      const i = steps.indexOf(state);
      if (i < steps.length - 1) move(steps[i + 1]);
      return;
    }
    if (event === 'BACK') {
      const i = steps.indexOf(state);
      if (i > 0) move(steps[i - 1]);
      return;
    }
    if (event === 'FAIL' && state === 'payment') move('address');
  };
  const allowed = () => {
    if (state === 'idle') return ['NEXT'];
    if (state === 'cart' || state === 'address') return ['BACK','NEXT'];
    if (state === 'payment') return ['BACK','FAIL','NEXT'];
    return ['BACK'];
  };
  const subscribe = fn => { subs.add(fn); fn(state); return () => subs.delete(fn); };
  return { get state(){ return state; }, send, allowed, subscribe };
}
