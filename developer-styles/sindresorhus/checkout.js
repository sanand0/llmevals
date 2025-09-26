const STEPS = ['idle','cart','address','payment','done'];
const indexOf = state => STEPS.indexOf(state);

export function createCheckoutMachine(initial = 'idle') {
    let state = STEPS.includes(initial) ? initial : 'idle';
    const subscribers = new Set();
    const emit = () => subscribers.forEach(fn => fn(state));
    const allowed = () => {
        const idx = indexOf(state);
        const events = [];
        if (idx < STEPS.length - 1) events.push('NEXT');
        if (idx > 0) events.push('BACK');
        if (state === 'payment') events.push('FAIL');
        return events;
    };
    const send = event => {
        if (!allowed().includes(event)) return;
        const idx = indexOf(state);
        if (event === 'NEXT') state = STEPS[idx + 1];
        else if (event === 'BACK') state = STEPS[idx - 1];
        else state = 'address';
        emit();
    };
    const subscribe = fn => {
        subscribers.add(fn);
        fn(state);
        return () => subscribers.delete(fn);
    };
    return {get state(){return state;},send,allowed,subscribe};
}
