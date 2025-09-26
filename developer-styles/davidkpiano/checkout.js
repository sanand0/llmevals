const steps=["idle","cart","address","payment","done"],last=steps.length-1;
export function createCheckoutMachine(initial="idle"){
  let state=steps.includes(initial)?initial:"idle";
  const listeners=new Set(),notify=()=>listeners.forEach(fn=>fn(state));
  const shift=delta=>{
    const next=steps[steps.indexOf(state)+delta];
    if(!next||next===state)return;
    state=next; notify();
  };
  const transitions={
    NEXT:()=>shift(1),
    BACK:()=>shift(-1),
    FAIL:()=>{if(state==="payment"){state="address";notify();}}
  };
  return {
    get state(){return state;},
    send(e){transitions[e]?.();},
    allowed(){
      const index=steps.indexOf(state),events=[];
      if(index<last)events.push("NEXT");
      if(index>0)events.push("BACK");
      if(state==="payment")events.push("FAIL");
      return events;
    },
    subscribe(fn){listeners.add(fn); fn(state); return ()=>listeners.delete(fn);}
  };
}
