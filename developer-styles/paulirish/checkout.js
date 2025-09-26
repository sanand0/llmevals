const steps=["idle","cart","address","payment","done"];
const allowed={idle:["NEXT"],cart:["BACK","NEXT"],address:["BACK","NEXT"],payment:["BACK","NEXT","FAIL"],done:["BACK"]};
const nextState=(state,event)=>{const idx=steps.indexOf(state);if(event==="NEXT"&&idx<steps.length-1)return steps[idx+1];if(event==="BACK"&&idx>0)return steps[idx-1];if(event==="FAIL"&&state==="payment")return"address";return state;};
export function createCheckoutMachine(initial="idle"){
  let state=steps.includes(initial)?initial:"idle";
  const subs=new Set();
  const machine={
    state,
    send:event=>{
      const next=nextState(state,event);
      if(next===state)return;
      state=machine.state=next;
      subs.forEach(fn=>fn(state));
    },
    allowed:()=>allowed[state].slice(),
    subscribe:fn=>{
      subs.add(fn);
      fn(state);
      return()=>subs.delete(fn);
    }
  };
  return machine;
}
