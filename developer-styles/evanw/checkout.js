const graph={
  idle:{NEXT:"cart"},
  cart:{NEXT:"address",BACK:"idle"},
  address:{NEXT:"payment",BACK:"cart"},
  payment:{NEXT:"done",BACK:"address",FAIL:"address"},
  done:{BACK:"payment"}
};
export function createCheckoutMachine(initial="idle"){
  let state=graph[initial]?initial:"idle";
  const watchers=new Set(),notify=s=>watchers.forEach(fn=>fn(s));
  const api={
    get state(){return state;},
    send(event){
      const next=graph[state]?.[event];
      if(next&&next!==state){
        state=next;
        notify(state);
      }
    },
    allowed(){
      return Object.keys(graph[state]||{});
    },
    subscribe(fn){
      watchers.add(fn);
      fn(state);
      return()=>watchers.delete(fn);
    }
  };
  return api;
}
