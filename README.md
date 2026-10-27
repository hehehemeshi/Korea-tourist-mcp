# Du lịch Hàn Quốc — MCP cho ChatGPT

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/hehehemeshi/Korea-tourist-mcp)

**Mặc định dùng nguồn mở, không cần API key nhà cung cấp.** Python 3.12, FastMCP Streamable HTTP tại `/mcp`, giao diện di động tiếng Việt tại `/`.

## Bản đồ bus tự động, không cần đăng ký API key

[PUBLIC_BUS.md](PUBLIC_BUS.md): Hai công cụ chọn nguồn theo vùng được hỏi hoặc tọa độ ChatGPT cung cấp; không mặc định Suwon. Seoul và GBIS đã có nguồn public-web kiểm chứng, vùng khác báo chưa tích hợp. Trang `/bus` không chọn sẵn vùng và không giữ bản đồ vùng trước làm kết quả mới. GPS Seoul có giờ đo/kiểm tra độ mới; GBIS là vị trí theo bến. Chưa phủ toàn Hàn Quốc.

## Nguồn menu và giá

[MENU_SOURCES.md](MENU_SOURCES.md): 5 hồ sơ nguồn thật, 15 mục menu/giá, công cụ get_restaurant_sources và adapter đọc bảng Suwon/website JSON-LD. Giá và policy từ bài cũ vẫn unverified; không tự gán cho quán trùng tên.

## Nhà hàng v2

Xem [RESTAURANTS.md](RESTAURANTS.md) để dùng `search_nearby_restaurants`, `get_restaurant_menu`, `get_order_policy`, `rank_restaurants`, nhập GPS trên điện thoại và bổ sung bằng chứng menu/giá/quy định. Không cần key để bắt đầu; Kakao ưu tiên nếu đã có key. Menu, chính sách hoặc rating chưa có nguồn sẽ là unknown — không phải dữ liệu đã được tự thu thập.

## Chức năng hiện tại

| Chức năng | Nguồn mặc định | Giới hạn |
|---|---|---|
| Tìm địa điểm, địa chỉ, ga | OpenStreetMap qua Photon | Dữ liệu cộng đồng, phạm vi Hàn Quốc; có thể thiếu địa điểm/ga, không có mã ga chính thức |
| Tìm địa điểm gần tọa độ | OpenStreetMap qua Overpass | Bán kính tối đa 5 km; tối đa 30 kết quả, chưa xếp theo khoảng cách |
| Chỉ đường metro / ô tô | Liên kết Google Maps | Mở Google để xem; MCP chưa đọc tuyến, thời gian đi, chuyển tuyến hay giá từ Google |
| Tìm lễ hội / khách sạn | Liên kết tìm kiếm Google | Chưa phải kết quả lễ hội hay phòng trống đã xác minh |
| Tàu sắp đến trực tiếp | Seoul, nếu đã thêm khóa | Thiếu khóa sẽ báo unavailable; không có dữ liệu trực tiếp giả |
| Lịch tàu KORAIL | TAGO, nếu đã thêm khóa | Lịch dự kiến, không phải thời gian thực |
| Tuyến và chuyển tuyến trong MCP | NETWORK_FILE đã xác minh, nếu cấu hình | Nếu chưa có đồ thị chỉ trả link Google Maps |
| Số sân ga | Không có nguồn xác minh | Luôn để null; không suy đoán từ chiều tàu, cửa tàu hay tag cộng đồng |

21 công cụ MCP (gồm hai công cụ bản đồ bus theo vùng): `search_stations`, `get_arrivals`, `plan_route`, `search_rail_stations`, `get_rail_schedule`, `search_tourism`, `nearby_tourism`, `tourism_detail`, `search_festivals`, `search_stays`, `search_places`, `geocode_address`, `get_driving_route`, `get_google_maps_links`.

`tourism_detail` và mã ga TAGO vẫn cần khóa của nguồn tương ứng. OSM không cung cấp các mã KTO/TAGO thay thế. Không có công cụ đặt vé, đặt phòng hay gọi taxi.

## Triển khai từ điện thoại, không cần máy tính

1. Mã đã có trong repository này. Bấm **Deploy to Render** và đăng nhập Render qua GitHub.
2. Blueprint dùng gói **Free** nếu tài khoản/khu vực hỗ trợ. Máy chủ có thể ngủ, gây khởi động chậm. Chỉ chọn gói trả phí nếu bạn chấp nhận giá hiện hành.
3. Bấm **Deploy Blueprint**; không cần nhập các khóa Seoul/KTO/Kakao/Naver. ACCESS_TOKEN được Render tự tạo cho REST API; Blueprint mới đặt MCP_PUBLIC=true cho MCP chỉ đọc công khai để thêm vào ChatGPT bằng No authentication. Dịch vụ cũ cần cập nhật biến này trên Render.
4. Kiểm tra `https://TEN.onrender.com/healthz` trả `ok`. Đây chỉ là sức khỏe máy chủ, không đảm bảo nguồn công cộng đang hoạt động.
5. Xem [CHATGPT.md](CHATGPT.md) để chọn cách xác thực rồi thêm URL `/mcp` vào ChatGPT.
6. Trong giao diện web `/`, nhập ACCESS_TOKEN từ Render để tìm địa điểm hoặc ga. Không gửi token qua lời nhắn ChatGPT, commit hoặc query URL.

Các REST endpoint tương ứng: `/api/places?query=`, `/api/stations?query=`, `/api/geocode?address=`, `/api/nearby?longitude=&latitude=&radius=`, `/api/route?origin=&destination=`, `/api/google?query=`, `/api/arrivals?station=`, `/api/rail-stations?city_code=11`, `/api/rail?origin=NODEID&destination=NODEID&date=YYYYMMDD`. `/api/tourism`, `/api/festivals`, `/api/stays`, `/api/tourism-detail` tương ứng các công cụ cùng tên.

## Nguồn mở và Google

- [OpenStreetMap](https://www.openstreetmap.org/copyright): dữ liệu cộng đồng theo ODbL, luôn ghi công tác giả; không phải dữ liệu cơ quan giao thông chính thức.
- [Photon](https://github.com/komoot/photon): demo API công cộng cho phép mức sử dụng hợp lý, không cam kết uptime. Tìm kiếm giới hạn bbox Hàn Quốc và lọc countrycode KR. Tên tiếng Anh và Hàn thường phù hợp hơn tiếng Việt.
- [Overpass](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html): truy vấn POI gần tọa độ, không lấy nền bản đồ hoặc đọc dữ liệu tàu trực tiếp.
- [Google Maps URLs](https://developers.google.com/maps/documentation/urls/get-started): không cần Google API key. Chỉ tạo link tìm kiếm/chỉ đường; không scrape, không trả dữ liệu Google giả. Google Maps Platform API vẫn cần khóa và có thể tính phí.

Các yêu cầu công cộng dùng User-Agent nhận diện dự án, bộ nhớ đệm tối đa 128 truy vấn / 1 giờ, khoảng cách ít nhất 2 giây và tối đa 300 yêu cầu/ngày trên mỗi tiến trình. Chạy **một worker, một replica** khi dùng máy chủ demo. Muốn mở rộng phải tự host hoặc chọn nhà cung cấp phù hợp; không nhân bản tiến trình để vượt hạn mức. Cache không có bản ghi ngoài bộ nhớ và mất khi restart. Kết quả hiển thị riêng thời điểm truy vấn (`fetched_at`) và lúc tải dữ liệu (`retrieved_at`), trạng thái cached; thời điểm tải không phải thời điểm địa điểm được chỉnh sửa. Overpass giữ `source_updated_at` nếu nguồn có cung cấp.

Nếu Photon/Overpass gặp lỗi, tìm kiếm trả link Google rõ ràng, không giả vờ đã tìm được địa điểm. Không dùng Nominatim public làm fallback. Chỉ truy vấn theo thao tác người dùng, không autocomplete hoặc tải hàng loạt.

## Bổ sung nguồn chính thức sau này

Trong Render → Environment, thêm các biến cần dùng (xem `.env.example`).

| Biến | Dịch vụ |
|---|---|
| SEOUL_API_KEY | [Ga Seoul OA-15442](https://data.seoul.go.kr/dataList/OA-15442/A/1/datasetView.do) |
| SEOUL_SUBWAY_API_KEY | [Tàu đến Seoul OA-12764](https://data.seoul.go.kr/dataList/OA-12764/A/1/datasetView.do) — khóa metro riêng |
| DATA_GO_KR_KEY | [MOLIT TAGO](https://www.data.go.kr/data/15098552/openapi.do) — bản Decoding |
| KTO_API_KEY | [KTO EngService2](https://www.data.go.kr/data/15101753/openapi.do) — bản Decoding |
| KAKAO_REST_API_KEY | [Kakao Local](https://developers.kakao.com/docs/en/local/dev-guide) |
| NAVER_CLIENT_ID, NAVER_CLIENT_SECRET | [Naver Maps](https://api.ncloud-docs.com/docs/en/application-maps-overview) |

`OPEN_DATA_FIRST=true` mặc định. Đặt `false` để chọn Seoul/KTO/Kakao/Naver cho chức năng đã có khóa; chức năng thiếu khóa vẫn dùng OSM hoặc link Google. Riêng tàu trực tiếp và TAGO luôn cần nguồn chính thức, không chuyển sang số liệu cộng đồng. Seoul tính ETA từ recptnDt + barvlDt; bản ghi quá 120 giây, tương lai hơn 30 giây, thiếu thời gian, ước tính không hợp lệ hoặc tàu đã rời ga không có ETA.

## Đồ thị tuyến tùy chọn

`NETWORK_FILE` trỏ JSON có `source` URL cơ quan chính thức, `verified_on` YYYY-MM-DD (không quá 90 ngày) và `edges`: mỗi cạnh có `from`, `to`, `kind` (`ride` hoặc `transfer`), `seconds` dương. Dùng mã nút riêng cho từng ga/tuyến. Chỉ thêm cạnh ngược và chuyển tuyến khi đã kiểm chứng; không suy từ thứ tự mã ga hoặc trùng tên. Không thêm trường sân ga chưa được xác minh. Người duy trì phải xác minh mỗi cạnh; URL nguồn không tự chứng minh nội dung. Đồ thị không gồm chờ tàu, lịch tàu cuối, gián đoạn hoặc hạn chế tiếp cận. Không có đồ thị mạng tự bịa được đóng gói.

## Kiểm thử và phát triển

```
python -m venv .venv
. .venv/bin/activate
pip install '.[test]'
pytest -q
uvicorn seoul_transit.app:app --host 0.0.0.0 --port 8000 --no-access-log
```

Có thể chạy các lệnh này trong GitHub Codespaces trên trình duyệt. `.env` không tự tải; dùng biến môi trường của hosting hoặc shell. GitHub Actions kiểm thử và build Docker mỗi lần push; không cần PAT trong mã. Tests giả lập feed để kiểm tra hợp đồng dữ liệu và tình huống lỗi, không phục vụ fixture như dữ liệu trực tiếp. Không đảm bảo uptime/độ đầy đủ của nguồn công cộng hoặc quyền truy cập các API có khóa. Không bật HTTP debug logs vì khóa nguồn chính thức nằm trong URL.

Output quán ăn 0.5.0: [OUTPUT.md](OUTPUT.md). Tọa độ do ChatGPT truyền vào, tối đa 10 quán gần đến xa, menu Hàn–Việt/giá/review hiển thị trực tiếp, bản đồ chung; thiếu dữ liệu ghi “Chưa có thông tin”. Refresh/Scan Tools sau khi triển khai để nhận metadata bản đồ.

