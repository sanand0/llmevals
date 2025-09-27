export function createCheckoutMachine(initial = 'idle') {
  const order = ['idle', 'cart', 'address', 'payment', 'done']
  let state = order.includes(initial) ? initial : 'idle'
  const subs = new Set()
  const notify = () => subs.forEach(fn => fn(state))
  const allowed = () => { const i = order.indexOf(state), ev = []; if (state !== 'done') ev.push('NEXT'); if (i > 0) ev.push('BACK'); if (state === 'payment') ev.push('FAIL'); return ev }
  const send = e => {
    if (e === 'NEXT') { const i = order.indexOf(state); if (i < order.length - 1) { state = order[i + 1]; notify() } }
    else if (e === 'BACK') { const i = order.indexOf(state); if (i > 0) { state = order[i - 1]; notify() } }
    else if (e === 'FAIL' && state === 'payment') { state = 'address'; notify() }
  }
  const subscribe = fn => { subs.add(fn); fn(state); return () => subs.delete(fn) }
  return { get state() { return state }, send, allowed, subscribe }
}

