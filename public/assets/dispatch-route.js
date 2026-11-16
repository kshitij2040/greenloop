/* Offline coordinate estimates for Dispatch. The C++ road-graph planner is separate. */
'use strict';
function dispatchRoute(depot, stops) {
  if (!stops.length || stops.length > 300) throw Error('Choose between 1 and 300 stops.');
  const points = [depot, ...stops];
  for (const p of points) {
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon) || Math.abs(p.lat)>90 || Math.abs(p.lon)>180)
      throw Error('Enter valid coordinates.');
  }
  const radians = Math.PI/180;
  const distance = (a,b) => {
    const h = Math.sin((b.lat-a.lat)*radians/2)**2 +
      Math.cos(a.lat*radians)*Math.cos(b.lat*radians)*Math.sin((b.lon-a.lon)*radians/2)**2;
    return 12742000*Math.asin(Math.sqrt(Math.min(1,Math.max(0,h))));
  };
  const d = points.map(a=>points.map(b=>distance(a,b)));
  const cost = order => order.reduce((sum,j,i)=>sum+d[order[i-1]??0][j],0)+d[order.at(-1)??0][0];
  const n=stops.length, unseen=new Set(stops.map((_,i)=>i+1)), baseline=[];
  let last=0;
  while(unseen.size){
    let best;
    for(const j of unseen) if(best===undefined||d[last][j]<d[last][best])best=j;
    baseline.push(best);unseen.delete(best);last=best;
  }
  const isExact=n<=12;
  let order=baseline.slice();
  if(isExact){
    const full=(1<<n)-1;
    const dp=new Float64Array((full+1)*n).fill(Infinity);
    const prev=new Int8Array(dp.length).fill(-1);
    for(let j=0;j<n;j++)dp[(1<<j)*n+j]=d[0][j+1];
    for(let mask=1;mask<=full;mask++)for(let j=0;j<n;j++){
      const current=dp[mask*n+j];if(!Number.isFinite(current))continue;
      for(let k=0;k<n;k++)if(!(mask&(1<<k))){
        const slot=(mask|(1<<k))*n+k, next=current+d[j+1][k+1];
        if(next<dp[slot]){dp[slot]=next;prev[slot]=j;}
      }
    }
    let j=0;
    for(let k=1;k<n;k++)if(dp[full*n+k]+d[k+1][0]<dp[full*n+j]+d[j+1][0])j=k;
    order=[];
    for(let mask=full;j>=0;){
      order.push(j+1);const before=prev[mask*n+j];mask^=1<<j;j=before;
    }
    order.reverse();
  }else{
    // Symmetric distances: reversing a segment changes just its two boundary legs.
    for(let pass=0;pass<12;pass++){
      let improvement=0, first=-1, end=-1;
      for(let i=0;i<n-1;i++)for(let j=i+1;j<n;j++){
        const a=order[i-1]??0,b=order[i],c=order[j],e=order[j+1]??0;
        const gain=d[a][b]+d[c][e]-d[a][c]-d[b][e];
        if(gain>improvement+1e-7){improvement=gain;first=i;end=j;}
      }
      if(first<0)break;
      order.splice(first,end-first+1,...order.slice(first,end+1).reverse());
    }
  }
  return {method:isExact?'Exact (Held–Karp)':'Heuristic (nearest neighbour + 2-opt)',
          metres:cost(order), baselineMetres:cost(baseline),
          stops:order.map(j=>stops[j-1])};
}
if(typeof module!=='undefined')module.exports=dispatchRoute;
