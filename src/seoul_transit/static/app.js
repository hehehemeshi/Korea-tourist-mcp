const $=id=>document.getElementById(id);
let mode='restaurants/rank';
const forms={
 'restaurants/rank':['Tìm quán trong ngân sách · Bằng chứng rõ ràng', [['longitude','Kinh độ GPS','127.001','number'],['latitude','Vĩ độ GPS','37.267','number'],['radius','Bán kính chim bay (m)','500','number'],['budget_krw_per_person','Ngân sách KRW/người','10000','number'],['party_size','Số người ăn','1','number'],['query','Tên quán tiếng Hàn hoặc Anh (không bắt buộc)','','text']]],
 'restaurants/menu':['Menu và giá có nguồn', [['restaurant_id','Mã quán từ kết quả tìm kiếm','osm:node:123','text']]],
 'restaurants/policy':['Quy định gọi món có bằng chứng riêng', [['restaurant_id','Mã quán từ kết quả tìm kiếm','osm:node:123','text']]],
 places:['Tìm địa điểm · OSM', [['query','Tên địa điểm tiếng Anh hoặc Hàn','Gyeongbokgung','text']]],
 stations:['Tìm ga · OSM', [['query','Tên ga tiếng Anh hoặc Hàn','Gangnam','text']]],
 nearby:['Địa điểm gần tọa độ · OSM', [['longitude','Kinh độ','126.978','number'],['latitude','Vĩ độ','37.5665','number'],['radius','Bán kính (mét, tối đa 5000)','2000','number']]],
 geocode:['Tìm địa chỉ · OSM', [['address','Địa chỉ tại Hàn Quốc','Seoul','text']]],
 route:['Mở chỉ đường Google Maps', [['origin','Điểm đi','Seoul Station','text'],['destination','Điểm đến','Hongik University Station','text']]],
 arrivals:['Tàu sắp đến · Cần khóa Seoul', [['station','Tên ga tiếng Hàn','강남','text']]],
 rail:['Lịch tàu · Cần khóa TAGO', [['origin','Mã nodeid TAGO ga đi','','text'],['destination','Mã nodeid TAGO ga đến','','text'],['date','Ngày khởi hành','','date']]]
};
function configure(){
 $('heading').textContent=forms[mode][0];$('fields').replaceChildren();$('gps').hidden=!['nearby','restaurants/rank'].includes(mode);$('gps-status').textContent='';
 for(const [name,title,placeholder,type] of forms[mode][1]){
  const label=document.createElement('label');label.textContent=title;
  const input=document.createElement('input');input.name=name;input.placeholder=placeholder;input.type=type;input.required=!(mode==='restaurants/rank'&&name==='query');
  if(type==='number')input.step='any';
  if(name==='radius'){input.min=1;input.max=5000;input.step=1;input.value=mode==='restaurants/rank'?'500':'2000';}
  if(name==='budget_krw_per_person'){input.min=1;input.step=1;input.value='10000';}
  if(name==='party_size'){input.min=1;input.max=20;input.step=1;input.value='1';}
  label.append(input);$('fields').append(label);
 }
}
for(const button of document.querySelectorAll('nav button'))button.onclick=()=>{mode=button.dataset.mode;configure();};
$('gps').onclick=()=>{
 const fields=$('fields');
 if(!navigator.geolocation){$('gps-status').textContent='Trình duyệt chưa hỗ trợ GPS. Nhập tọa độ thủ công.';return;}
 $('gps-status').textContent='Đang xin quyền vị trí từ trình duyệt…';
 navigator.geolocation.getCurrentPosition(position=>{
  if(!$('fields').contains(fields.querySelector('[name=longitude]')))return;
  fields.querySelector('[name=longitude]').value=position.coords.longitude;
  fields.querySelector('[name=latitude]').value=position.coords.latitude;
  $('gps-status').textContent='Đã lấy GPS (sai số khoảng '+Math.round(position.coords.accuracy)+' m). Tọa độ chỉ được gửi khi bạn bấm Tra cứu.';
 },()=>{$('gps-status').textContent='Chưa lấy được GPS. Cho phép vị trí hoặc nhập tọa độ từ bản đồ.';},{enableHighAccuracy:true,timeout:10000,maximumAge:30000});
};
function paragraph(parent,value){const p=document.createElement('p');p.textContent=value;parent.append(p);}
function addLink(parent,label,url){
 try{const parsed=new URL(url);if(parsed.protocol!=='https:')return;const a=document.createElement('a');a.textContent=label;a.href=parsed.href;a.target='_blank';a.rel='noopener noreferrer';const p=document.createElement('p');p.append(a);parent.append(p);}catch{}
}
const fieldNames={name:'Tên quán',address:'Địa chỉ',longitude:'Kinh độ',latitude:'Vĩ độ',straight_line_distance_m:'Khoảng cách chim bay (m)',walking_distance_m:'Quãng đường đi bộ (m)',walking_duration_seconds:'Đi bộ dự kiến (giây)',name_ko:'Tên món tiếng Hàn',name_vi:'Tên món tiếng Việt',price_krw:'Giá KRW',minimum_servings:'Số suất tối thiểu',one_item_per_person:'Mỗi người một món',solo_allowed:'Cho phép khách đi một mình',minimum_order_krw:'Tiền món tối thiểu',mandatory_extra_krw:'Phụ phí bắt buộc/nhóm',open_now:'Đang mở cửa',opening_hours:'Giờ mở cửa',total_krw:'Tổng KRW tính theo điều kiện đã biết'};
function renderValue(parent,key,value){
 if(typeof value==='string'&&(key==='url'||key.endsWith('_url'))){addLink(parent,'Mở nguồn / chỉ đường',value);return;}
 if(value&&typeof value==='object'&&!Array.isArray(value)&&'value' in value&&'status' in value){
  const status={verified:'Đã xác minh',unverified:'Chưa xác minh',unknown:'Chưa biết'}[value.status]||value.status;
  paragraph(parent,(fieldNames[key]||key)+': '+(value.value===null?'Chưa có dữ liệu':String(value.value))+' · '+status);
  if(value.checked_at)paragraph(parent,'Kiểm tra lúc: '+value.checked_at);
  if(value.source_updated_at)paragraph(parent,'Nguồn cập nhật: '+value.source_updated_at);
  if(value.source_url)addLink(parent,'Bằng chứng / nguồn',value.source_url);
  if(typeof value.value==='string'&&value.value.startsWith('https://'))addLink(parent,'Mở liên kết gốc',value.value);
  return;
 }
 if(Array.isArray(value)||value&&typeof value==='object'){
  const box=document.createElement('details');const summary=document.createElement('summary');summary.textContent=fieldNames[key]||key;box.append(summary);
  for(const [k,v] of Object.entries(value))renderValue(box,k,v);
  parent.append(box);return;
 }
 paragraph(parent,(fieldNames[key]||key)+': '+(value===null?'Chưa có dữ liệu':String(value)));
}
$('search').onsubmit=async event=>{
 event.preventDefault();const submit=event.submitter;submit.disabled=true;$('results').replaceChildren();
 const requestedMode=mode;
 paragraph($('results'),'Đang tra cứu…');
 const params=new URLSearchParams(new FormData($('search')));
 if(requestedMode==='rail')params.set('date',params.get('date').replaceAll('-',''));
 try{
  const response=await fetch('/api/'+requestedMode+'?'+params,{headers:$('token').value?{Authorization:'Bearer '+$('token').value}:{}});
  if(!response.ok)throw Error(response.status===401?'Mã truy cập máy chủ không đúng.':'Không thể kết nối máy chủ hoặc dữ liệu nhập không hợp lệ.');
  const data=await response.json();$('results').replaceChildren();
  paragraph($('results'),data.message||data.note||(data.status==='no_data'?'Không tìm thấy kết quả.':'Kết quả tra cứu'));
  if(data.data_kind==='external_links_only')paragraph($('results'),'Chưa lấy kết quả từ Google. Bấm liên kết để xem trực tiếp.');
  for(const [key,label] of [['fetched_at','Truy vấn lúc'],['retrieved_at','Dữ liệu được tải lúc']])if(data[key])paragraph($('results'),label+': '+new Date(data[key]).toLocaleString('vi-VN',{timeZone:'Asia/Seoul'})+' (KST)');
  if(data.cached)paragraph($('results'),'Đang dùng bộ nhớ đệm (tối đa 1 giờ).');
  if(data.attribution)paragraph($('results'),data.attribution);
  if(data.source)addLink($('results'),'Nguồn dữ liệu / tài liệu',data.source);
  for(const link of data.links||[])addLink($('results'),link.label,link.url);
  if(data.coverage)paragraph($('results'),'Phạm vi: '+data.coverage);
  const rows=Array.isArray(data.data)?data.data:data.data?[data.data]:[];
  for(const row of rows){
   const card=document.createElement('article');
   const labels={station:'Ga',line:'Tuyến',name:'Tên',name_ko:'Tên tiếng Hàn',address:'Địa chỉ',longitude:'Kinh độ',latitude:'Vĩ độ',direction:'Chiều',towards:'Hướng đi',destination:'Đến',message:'Thông báo gốc',generated_at:'Nguồn cập nhật',source_updated_at:'OSM chỉnh sửa',estimated_arrival:'Dự kiến đến',freshness:'Độ mới',platform:'Sân ga',platform_status:'Xác minh sân ga',scheduled_departure:'Khởi hành theo lịch',scheduled_arrival:'Đến theo lịch'};
   for(const [key,value] of Object.entries(row)){
    if(value&&typeof value==='object'){renderValue(card,key,value);continue;}
    if(key.endsWith('_url')&&value){addLink(card,key==='google_maps_url'?'Mở Google Maps':'Xem dữ liệu gốc',value);continue;}
    paragraph(card,(labels[key]||key)+': '+(value===null?'Chưa xác minh / không có dữ liệu':typeof value==='object'?JSON.stringify(value):String(value)));
   }
   $('results').append(card);
  }
 }catch(error){$('results').replaceChildren();paragraph($('results'),error.message);}finally{submit.disabled=false;}
};
configure();
