const $=id=>document.getElementById(id);
let mode='places';
const forms={
 places:['Tìm địa điểm · OSM', [['query','Tên địa điểm tiếng Anh hoặc Hàn','Gyeongbokgung','text']]],
 stations:['Tìm ga · OSM', [['query','Tên ga tiếng Anh hoặc Hàn','Gangnam','text']]],
 nearby:['Địa điểm gần tọa độ · OSM', [['longitude','Kinh độ','126.978','number'],['latitude','Vĩ độ','37.5665','number'],['radius','Bán kính (mét, tối đa 5000)','2000','number']]],
 geocode:['Tìm địa chỉ · OSM', [['address','Địa chỉ tại Hàn Quốc','Seoul','text']]],
 route:['Mở chỉ đường Google Maps', [['origin','Điểm đi','Seoul Station','text'],['destination','Điểm đến','Hongik University Station','text']]],
 arrivals:['Tàu sắp đến · Cần khóa Seoul', [['station','Tên ga tiếng Hàn','강남','text']]],
 rail:['Lịch tàu · Cần khóa TAGO', [['origin','Mã nodeid TAGO ga đi','','text'],['destination','Mã nodeid TAGO ga đến','','text'],['date','Ngày khởi hành','','date']]]
};
function configure(){
 $('heading').textContent=forms[mode][0];$('fields').replaceChildren();
 for(const [name,title,placeholder,type] of forms[mode][1]){
  const label=document.createElement('label');label.textContent=title;
  const input=document.createElement('input');input.name=name;input.placeholder=placeholder;input.type=type;input.required=true;
  if(type==='number')input.step='any';
  if(name==='radius'){input.min=1;input.max=5000;input.step=1;input.value='2000';}
  label.append(input);$('fields').append(label);
 }
}
for(const button of document.querySelectorAll('nav button'))button.onclick=()=>{mode=button.dataset.mode;configure();};
function paragraph(parent,value){const p=document.createElement('p');p.textContent=value;parent.append(p);}
function addLink(parent,label,url){
 try{const parsed=new URL(url);if(parsed.protocol!=='https:')return;const a=document.createElement('a');a.textContent=label;a.href=parsed.href;a.target='_blank';a.rel='noopener noreferrer';const p=document.createElement('p');p.append(a);parent.append(p);}catch{}
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
  for(const row of data.data||[]){
   const card=document.createElement('article');
   const labels={station:'Ga',line:'Tuyến',name:'Tên',name_ko:'Tên tiếng Hàn',address:'Địa chỉ',longitude:'Kinh độ',latitude:'Vĩ độ',direction:'Chiều',towards:'Hướng đi',destination:'Đến',message:'Thông báo gốc',generated_at:'Nguồn cập nhật',source_updated_at:'OSM chỉnh sửa',estimated_arrival:'Dự kiến đến',freshness:'Độ mới',platform:'Sân ga',platform_status:'Xác minh sân ga',scheduled_departure:'Khởi hành theo lịch',scheduled_arrival:'Đến theo lịch'};
   for(const [key,value] of Object.entries(row)){
    if(key.endsWith('_url')&&value){addLink(card,key==='google_maps_url'?'Mở Google Maps':'Xem dữ liệu gốc',value);continue;}
    paragraph(card,(labels[key]||key)+': '+(value===null?'Chưa xác minh / không có dữ liệu':typeof value==='object'?JSON.stringify(value):String(value)));
   }
   $('results').append(card);
  }
 }catch(error){$('results').replaceChildren();paragraph($('results'),error.message);}finally{submit.disabled=false;}
};
configure();
