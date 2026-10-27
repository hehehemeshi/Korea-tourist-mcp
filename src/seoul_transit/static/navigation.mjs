// All positions stay on the device. Manual stage confirmation avoids inferring boarding.
export const radians=x=>x*Math.PI/180;
export function distance(a,b){const dy=radians(b.latitude-a.latitude),dx=radians(b.longitude-a.longitude),v=Math.sin(dy/2)**2+Math.cos(radians(a.latitude))*Math.cos(radians(b.latitude))*Math.sin(dx/2)**2;return 6371000*2*Math.atan2(Math.sqrt(v),Math.sqrt(Math.max(0,1-v)));}
export function decodePolyline(encoded){
 if(typeof encoded!=='string'||encoded.length>200000)return [];
 let i=0,lat=0,lng=0,points=[];
 try{while(i<encoded.length){let pair=[];for(let j=0;j<2;j++){let shift=0,result=0,b;do{if(i>=encoded.length||shift>30)throw Error();b=encoded.charCodeAt(i++)-63;if(b<0||b>63)throw Error();result|=(b&31)<<shift;shift+=5;}while(b>=32);pair.push(result&1?~(result>>1):result>>1);}lat+=pair[0];lng+=pair[1];const p={latitude:lat/1e5,longitude:lng/1e5};if(Math.abs(p.latitude)>90||Math.abs(p.longitude)>180)throw Error();points.push(p);if(points.length>30000)throw Error();}}catch{return [];}return points;
}
export function lineDistance(p,line){if(line.length<2)return null;const k=111195,c=Math.cos(radians(p.latitude));let best=Infinity;for(let i=1;i<line.length;i++){const a={x:(line[i-1].longitude-p.longitude)*k*c,y:(line[i-1].latitude-p.latitude)*k},b={x:(line[i].longitude-p.longitude)*k*c,y:(line[i].latitude-p.latitude)*k},dx=b.x-a.x,dy=b.y-a.y,t=Math.max(0,Math.min(1,-(a.x*dx+a.y*dy)/(dx*dx+dy*dy||1)));best=Math.min(best,Math.hypot(a.x+t*dx,a.y+t*dy));}return best;}
export function newNavigationState(){return {near:0,off:0,nearSince:0,offSince:0,arrived:false,lastAlert:0,lastFix:0};}
export function evaluatePosition(fix,step,state,now=Date.now()){
 const accuracy=fix?.coords?.accuracy,age=now-fix?.timestamp;
 if(!fix||!Number.isFinite(age)||age< -5000||age>20000||!Number.isFinite(accuracy)||accuracy<0||accuracy>60||!Number.isFinite(fix.coords.latitude)||!Number.isFinite(fix.coords.longitude)){
  state.near=state.off=0;return {status:'unreliable',message:'GPS yếu hoặc đã cũ. Không suy đoán chặng đi; kiểm tra tên ga/bến.'};
 }
 if(fix.timestamp<=state.lastFix)return {status:'duplicate'};state.lastFix=fix.timestamp;
 if(!step?.end)return {status:'ready'};
 const position={latitude:fix.coords.latitude,longitude:fix.coords.longitude},away=distance(position,step.end);
 if(away<=120){if(!state.near)state.nearSince=now;state.near++;}else state.near=0;
 if(!state.arrived&&state.near>=2&&now-state.nearSince>=2000){state.arrived=true;return {status:'near_stop',message:step.mode==='TRANSIT'?`Bạn đang gần điểm xuống ${step.arrival_stop?.name||''}. Kiểm tra biển và thông báo trên xe; chuẩn bị xuống nếu đúng chặng.`:'Bạn đang gần cuối chặng đi bộ. Kiểm tra điểm chuyển và xác nhận chặng tiếp theo.'};}
 const deviation=lineDistance(position,decodePolyline(step.encoded_polyline));
 if(deviation!==null&&deviation>Math.max(180,accuracy*3)){if(!state.off)state.offSince=now;state.off++;}else state.off=0;
 if(state.off>=3&&now-state.offSince>=10000&&now-state.lastAlert>120000){state.lastAlert=now;return {status:'possible_deviation',message:'Bạn có thể đang lệch hành trình dự kiến. Kiểm tra chặng đang chọn và biển ga/bến; có thể tra cứu lại từ vị trí hiện tại.'};}
 return {status:'tracking',distance_to_step_end_m:Math.round(away)};
}
