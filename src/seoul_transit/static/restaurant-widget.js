(()=>{
'use strict';
const missing='Chưa có thông tin',$=id=>document.getElementById(id);
let mapData={origin:null,restaurants:[]},zoom=16,center=[0,0],drag=null,previous='';
const valid=p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)&&Math.abs(p[0])<=180&&Math.abs(p[1])<=85;
function project(p,z){const scale=256*2**z,lat=p[1]*Math.PI/180;return[(p[0]+180)/360*scale,(1-Math.log(Math.tan(lat)+1/Math.cos(lat))/Math.PI)/2*scale];}
function add(parent,tag,text,cls){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;parent.append(el);return el;}
function link(parent,label,href){try{const url=new URL(href);if(url.protocol!=='https:')return;const a=add(parent,'a',label);a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';}catch{}}
function draw(){
 const box=$('map'),w=box.clientWidth,h=box.clientHeight,n=2**zoom,base=[center[0]-w/2,center[1]-h/2];$('tiles').replaceChildren();$('pins').replaceChildren();
 if(!valid(mapData.origin)&&!mapData.restaurants.some(r=>valid(r.coordinates)))return;
 for(let x=Math.floor(base[0]/256);x<=Math.floor((base[0]+w)/256);x++)for(let y=Math.floor(base[1]/256);y<=Math.floor((base[1]+h)/256);y++){
  if(y<0||y>=n)continue;const img=document.createElement('img');img.className='tile';img.alt='';img.loading='lazy';img.referrerPolicy='strict-origin-when-cross-origin';img.style.left=(x*256-base[0])+'px';img.style.top=(y*256-base[1])+'px';img.src=`https://tile.openstreetmap.org/${zoom}/${(x%n+n)%n}/${y}.png`;$('tiles').append(img);
 }
 const points=[...(valid(mapData.origin)?[{coordinates:mapData.origin,name:'Vị trí ChatGPT cung cấp',number:'Bạn',origin:true}]:[]),...mapData.restaurants];
 for(const point of points){if(!valid(point.coordinates))continue;const xy=project(point.coordinates,zoom);const pin=add($('pins'),'button',String(point.number),'pin'+(point.origin?' origin':''));pin.style.left=(xy[0]-base[0])+'px';pin.style.top=(xy[1]-base[1])+'px';pin.title=point.name||missing;pin.setAttribute('aria-label',point.name||missing);pin.onpointerdown=e=>e.stopPropagation();pin.onclick=()=>document.getElementById('restaurant-'+point.number)?.scrollIntoView({behavior:'smooth',block:'start'});}
}
function fit(){
 const points=[mapData.origin,...mapData.restaurants.map(r=>r.coordinates)].filter(valid);if(!points.length){$('map-note').textContent=missing;return;}
 const normalized=points.map(p=>project(p,0));const min=[Math.min(...normalized.map(p=>p[0])),Math.min(...normalized.map(p=>p[1]))],max=[Math.max(...normalized.map(p=>p[0])),Math.max(...normalized.map(p=>p[1]))];
 zoom=Math.max(2,Math.min(18,Math.floor(Math.min(Math.log2(Math.max(100,$('map').clientWidth-90)/Math.max(.001,max[0]-min[0])),Math.log2(Math.max(100,$('map').clientHeight-80)/Math.max(.001,max[1]-min[1]))))));
 center=[(min[0]+max[0])/2*2**zoom,(min[1]+max[1])/2*2**zoom];draw();
}
function changeZoom(delta){const next=Math.max(2,Math.min(19,zoom+delta)),ratio=2**(next-zoom);center=center.map(v=>v*ratio);zoom=next;draw();}
$('plus').onclick=()=>changeZoom(1);$('minus').onclick=()=>changeZoom(-1);
$('map').onpointerdown=event=>{if(event.target.closest('button,a'))return;drag=[event.clientX,event.clientY,...center];$('map').setPointerCapture(event.pointerId);};
$('map').onpointermove=event=>{if(!drag)return;center=[drag[2]-(event.clientX-drag[0]),drag[3]-(event.clientY-drag[1])];draw();};
$('map').onpointerup=()=>{drag=null;};$('map').onpointercancel=()=>{drag=null;};
$('map').addEventListener('wheel',event=>{if(!event.ctrlKey)return;event.preventDefault();changeZoom(event.deltaY<0?1:-1);},{passive:false});
function render(output){
 const report=output?.presentation||output;if(!Array.isArray(report?.restaurants))return;
 const signature=JSON.stringify(report);if(signature===previous)return;previous=signature;
 const restaurants=report.restaurants.slice(0,10);$('cards').replaceChildren();$('state').textContent=`${restaurants.length} quán · gần đến xa · tối đa 10 quán`;
 $('map-note').textContent=report.notice||'Khoảng cách là đường chim bay. Nguồn thiếu thông tin được ghi rõ.';
 mapData={origin:null,restaurants:[]};
 for(const feature of report.map?.features||[]){if(feature.geometry?.type!=='Point')continue;const p=feature.properties||{};if(p.kind==='origin')mapData.origin=feature.geometry.coordinates;else if(p.kind==='restaurant')mapData.restaurants.push({...p,coordinates:feature.geometry.coordinates});}
 for(const c of restaurants){
  const card=add($('cards'),'article');card.id='restaurant-'+c.number;add(card,'h2',`${c.number}. ${c.name||missing}`);
  add(card,'p',`Khoảng cách: ${c.distance_display||missing} (đường chim bay) · Đi bộ: ${c.walking_distance_display||missing}`);
  add(card,'p','Địa chỉ: '+(c.address||missing));if(c.walking_directions_url)link(card,'Chỉ đường đi bộ',c.walking_directions_url);else add(card,'p','Chỉ đường đi bộ: '+missing);
  const scroll=add(card,'div',undefined,'table-scroll'),table=add(scroll,'table'),head=add(table,'thead'),tr=add(head,'tr');
  for(const title of ['Món tiếng Hàn','Tiếng Việt','Giá KRW','Đơn vị'])add(tr,'th',title);
  const body=add(table,'tbody');
  for(const item of c.menu?.length?c.menu:[{}]){
   const row=add(body,'tr');for(const text of [item.name_ko,item.name_vi,item.price_display,item.price_basis])add(row,'td',text||missing);
   if(item.price_krw!==undefined&&item.price_krw!==null&&item.price_evidence?.status!=='verified')add(card,'p','Giá niêm yết chưa xác minh hiện tại.','notice');
   if(item.translation_method==='literal_glossary_translation')add(card,'p','Tên Việt là bản dịch tên món, không xác nhận thành phần/dị ứng.','notice');
  }
  const review=c.reviews||{};add(card,'p','Điểm đánh giá: '+(review.rating_display||missing));add(card,'p','Số lượt đánh giá: '+(review.review_count_display||missing));add(card,'p','Nhận xét nổi bật: '+(review.summary||missing));
  if(review.rating!==null&&review.rating!==undefined&&review.rating_evidence?.status!=='verified')add(card,'p','Điểm đánh giá chưa xác minh hiện tại.','notice');
  const sources=[c.name_evidence,c.address_evidence,review.rating_evidence,review.count_evidence,...(c.menu||[]).map(m=>m.price_evidence),...(review.highlights||[]).map(h=>h.evidence)],seen=new Set();
  for(const source of sources){if(!source?.source_url||seen.has(source.source_url))continue;seen.add(source.source_url);const line=add(card,'p',undefined,'sources');link(line,'Nguồn',source.source_url);line.append(document.createTextNode(' · Kiểm tra: '+(source.checked_at||missing)));}
 }
 fit();if(window.openai?.notifyIntrinsicHeight)window.openai.notifyIntrinsicHeight({height:Math.min(1100,document.body.scrollHeight)});
}
window.renderRestaurantReport=render;
function fallback(){
 if(!location.hash)return;try{const raw=location.hash.slice(1).replace(/-/g,'+').replace(/_/g,'/');mapData=JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(raw+'='.repeat((4-raw.length%4)%4)),c=>c.charCodeAt(0))));mapData.restaurants=(mapData.restaurants||[]).slice(0,10);$('state').textContent='Bản đồ chung · Các số trùng thứ tự danh sách quán';$('map-note').textContent='Vị trí do ChatGPT cung cấp. Bản đồ không xác nhận quán đang mở hoặc có lối đi bộ.';for(const p of mapData.restaurants)add($('cards'),'p',`${p.number}. ${p.name||missing}`);fit();}catch{$('state').textContent=missing;}
}
window.addEventListener('message',event=>{
 if(event.source!==window.parent)return;const message=event.data;if(!message||message.jsonrpc!=='2.0')return;
 if(message.id==='korea-restaurant-init'&&message.result){window.parent.postMessage({jsonrpc:'2.0',method:'ui/notifications/initialized'},'*');return;}
 if(message.method==='ui/notifications/tool-result')render(message.params?.structuredContent||message.params?.result?.structuredContent);
});
window.addEventListener('openai:set_globals',event=>render(event.detail?.globals?.toolOutput));
if(window.openai?.toolOutput)render(window.openai.toolOutput);
if(window.parent!==window)window.parent.postMessage({jsonrpc:'2.0',id:'korea-restaurant-init',method:'ui/initialize',params:{appInfo:{name:'Korea Tourist Restaurants',version:'1.0.0'},appCapabilities:{},protocolVersion:'2026-01-26'}},'*');
fallback();window.addEventListener('resize',draw);
})();
