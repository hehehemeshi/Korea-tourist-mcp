# Korea Tourist MCP v2 — quán ăn theo GPS và ngân sách

Bản nâng cấp giữ các công cụ giao thông và bổ sung 4 công cụ chỉ đọc. Không cần đổi URL MCP. Sau khi Render deploy commit mới, **Refresh/Scan Tools** trong ChatGPT. `/healthz` có `version: 0.3.0` và `restaurant_tools: true` khi đã chạy bản này.

## Bắt đầu trên điện thoại

- Trong ChatGPT, cung cấp tọa độ WGS84 của chính bạn, hoặc dùng website máy chủ → **Quán ăn ₩10.000 → Dùng vị trí GPS của tôi**. Trình duyệt xin quyền riêng; MCP không tự truy cập GPS của ChatGPT/Android. Website chỉ gửi tọa độ sau khi bạn bấm Tra cứu. Nhập ACCESS_TOKEN để dùng REST như trước.
- Nhập **kinh độ trước, vĩ độ sau**, bán kính mặc định 500 m, ngân sách KRW/người và số người. Tên quán tùy chọn nhận Hangul/Anh và chuẩn hóa Unicode; không ép dịch sang tiếng Anh.
- Bán kính là đường chim bay. Máy chủ không tự tăng 500 m thành 1–2 km. Tọa độ điểm bản đồ có thể sai hoặc là tâm tòa nhà, không bảo đảm vị trí cửa vào.
- Với mỗi kết quả, xem `restaurant_id`, nguồn dữ liệu, giá, điều kiện gọi món và `assessment`. Không coi `status: ok` của tìm kiếm là xác nhận quán phù hợp.

## Công cụ và nguồn

| Công cụ | Nội dung |
|---|---|
| `search_nearby_restaurants(longitude, latitude, radius=500, budget_krw_per_person=10000, party_size=1, query='', limit=15, include_walking=false)` | Tìm quán đúng bán kính, không trả café/ga như nhà hàng. Kakao FD6 nếu có khóa → Overpass → Photon khi lỗi, kết quả rỗng hoặc không có quán trong vòng tròn. |
| `get_restaurant_menu(restaurant_id)` | Tên món Hàn/Việt, giá KRW, đơn vị tính, ảnh gốc và link menu nếu có bằng chứng. Không tự OCR, dịch, scrape hoặc điền giá từ trí nhớ. |
| `get_order_policy(restaurant_id)` | Chính sách riêng: số suất, một người một món, khách đi một mình, tiền món tối thiểu, phụ phí bắt buộc. Không suy từ tên món hay giá. |
| `rank_restaurants(...)` | Tìm và xếp hạng theo điều kiện có bằng chứng trước, rồi khoảng cách so sánh được, rating đã có nguồn làm tiêu chí phụ khi khoảng cách bằng nhau. Không gán điểm chất lượng khi thiếu đánh giá. |

REST tương ứng: `/api/restaurants`, `/api/restaurants/menu?restaurant_id=`, `/api/restaurants/policy?restaurant_id=`, `/api/restaurants/rank`. Các tham số tìm kiếm giống công cụ MCP.

- [Kakao Local](https://developers.kakao.com/docs/en/local/dev-guide#search-by-category): `category_group_code=FD6`, x/y, radius mét, sort distance, truy vấn tên Hàn khi có. Cần `KAKAO_REST_API_KEY`. Khóa không xuất hiện trong kết quả/lỗi. Không cung cấp menu/giá/minimum portions/ratings đáng tin cậy qua adapter này.
- [Overpass](https://dev.overpass-api.de/overpass-doc/en/): chỉ `amenity=restaurant|fast_food`, giữ giờ mở cửa và website:menu nếu có nhưng **unverified**. Timeout và kết quả partial cũng kích hoạt Photon.
- [Photon](https://github.com/komoot/photon): dùng reverse category khi không nhập tên quán (radius theo km); tìm tên dùng bbox nhỏ quanh GPS, lọc quốc gia KR, loại đối tượng và khoảng cách Haversine sau khi nhận dữ liệu. Không phải danh sách đầy đủ. Không trộn ID Kakao và OSM hoặc tự kết luận hai tên giống nhau là cùng quán.

Mỗi lần tìm dừng ở nguồn đầu tiên có kết quả hợp lệ; **không tuyên bố đã đối chiếu nhiều nguồn cho cùng một quán**. `provider_attempts` ghi lỗi/rỗng/thành công, thời điểm tải nếu có và trạng thái bị cắt. `no_data` không có nghĩa không có quán; `unavailable` là nguồn đều lỗi/chưa cấu hình. Luôn có link Google dự phòng, không scrape kết quả Google. Các truy vấn nguồn mở dùng cache/giới hạn chung hiện có; chạy một replica/worker như README.

## Menu, ảnh, chính sách: cách bổ sung bằng chứng

**Registry mặc định rỗng. Bản nâng cấp không tạo ra một kho menu/giá đã được thu thập sẵn.** Không có nguồn thì công cụ trả `unknown`, không cố trả lời “có” cho ngân sách ₩10.000.

Registry nằm ở [src/seoul_transit/data/restaurant_evidence.json](src/seoul_transit/data/restaurant_evidence.json). Có thể sửa bằng trình duyệt GitHub; Docker tự đóng gói file. JSON schema ở cùng thư mục, tên `restaurant_evidence.schema.json`. Hoặc dùng `RESTAURANT_EVIDENCE_FILE` để trỏ file JSON do quản trị viên cung cấp, cần tự COPY file đó vào Docker image.

1. Lấy ID từ kết quả thật: `kakao:...`, `osm:node:...`, `osm:way:...`, hoặc `osm:relation:...`. Không gán bằng chứng của quán cùng tên cho ID khác.
2. Ghi lại menu/ảnh gốc hoặc trang chính thức; xác nhận thông tin gọi món **riêng** với quán hoặc biển nội quy. Giữ URL HTTPS nguồn, trích đoạn cụ thể và thời điểm có múi giờ. Không gọi điện/nhắn tin tự động.
3. Mỗi trường là một Fact có `value`, `status`, `source_url`, `checked_at`, `source_updated_at` nếu biết, `method`, `evidence_excerpt`, `attribution`. Thời điểm mình kiểm tra không được ghi thành thời điểm quán cập nhật.
4. Chỉ dùng `verified` khi người duy trì đã đối chiếu trực tiếp: method `restaurant_official` hoặc `direct_observation`, có URL và trích đoạn, checked_at không tương lai và không quá 30 ngày. Quá hạn/thiếu bằng chứng tự hạ thành `unverified`. `verified` phản ánh bằng chứng do người duy trì rà soát, không phải máy chủ tự chứng thực website.
5. Menu items có `name_ko`, `name_vi`, `price_krw`, `price_basis` (`per_serving`, `per_person`, `per_set`), `serves_people` cho set, `minimum_servings` riêng từng món nếu có. Không có bản dịch đã ghi nguồn thì tên Việt để unknown. `menu_images` là danh sách Fact URL ảnh gốc; máy chủ không tải ảnh hoặc xác thực nội dung ảnh. Giao diện mở link gốc, không nhúng ảnh bên thứ ba.
6. Policy chung chỉ ghi những quy định áp dụng cho **mọi món**: `minimum_servings`, `one_item_per_person`, `solo_allowed`, `minimum_order_krw` (tiền món trước phụ phí), `mandatory_extra_krw` (tổng phụ phí bắt buộc cho nhóm). Nếu quy định phụ thuộc món, dùng `menu[].minimum_servings`; điều kiện khác phụ thuộc món mà chưa mô hình hóa thì để unknown, không gán policy chung.
7. `opening_hours` là lịch, không chứng minh đang mở. `open_now` phải có chứng cứ riêng trong 5 phút gần nhất. Chưa có bộ phân tích lịch mở cửa/ngày lễ/giờ nghỉ. Rating chỉ nhận điểm 0–5 kèm nguồn, thời gian và bằng chứng; không tự tạo review hay dùng điểm ngoài thang này.

Không có public write tool hoặc upload endpoint để khách bất kỳ sửa bằng chứng. Registry sai schema, trùng ID, giá âm, số suất không hợp lệ hoặc ngày thiếu múi giờ sẽ không được dùng để xác nhận thông tin. Dữ liệu cache restaurant gần đây chỉ phục vụ link menu và mất sau restart; giá/policy vẫn đọc lại từ registry mỗi lần.

## Ngân sách và số người: quyết định thận trọng

Mỗi quán có assessment:

- `meets_verified_constraints`: có ít nhất một món xác định được, giá/đơn vị/số suất và các chính sách bắt buộc đều có bằng chứng còn hạn, tổng tiền trong ngân sách nhóm. Đây là **kết luận có điều kiện theo bằng chứng**, không phải cam kết giá hiện tại hoặc quán đang mở.
- `does_not_meet_verified_constraints`: ví dụ quán đã xác nhận không tiếp khách một mình khi party_size=1.
- `insufficient_evidence`: thiếu giá, policy, phụ phí hoặc không tìm được phương án hợp lệ trong menu đã biết. Không tự điền unknown thành 0/false/1. Món đã biết quá đắt không chứng minh cả menu đều quá đắt.

Ví dụ tính toán trong tests dùng món **giả lập**, không phải dữ liệu quán thật: 1 người, ₩8.000/suất, tối thiểu 2 suất → ₩16.000; không phù hợp ngân sách ₩10.000. Quy định 2 suất không đồng nghĩa cấm 1 người. Tiền món tối thiểu phải tính tròn số món cần gọi, không giả vờ có thể trả đúng ngưỡng lẻ. Quy tắc món/set phức tạp, món bắt buộc đi kèm hoặc giảm giá chưa mô hình hóa phải được ghi unknown.

## Đi bộ và xếp hạng

`straight_line_distance_m` luôn ghi rõ geodesic. `walking_distance_m` và `walking_duration_seconds` mặc định unknown và có link đi bộ Google Maps cho đúng tọa độ. Không nhân khoảng cách chim bay thành đường đi bộ.

Có thể thêm `ORS_API_KEY` và gọi với `include_walking=true` để lấy **ước tính tuyến foot-walking** từ [openrouteservice](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/). Chỉ tối đa 5 quán đầu mỗi truy vấn. Khi thiếu key/lỗi/không có tuyến, khoảng cách đi bộ vẫn unknown. Chưa kiểm chứng live adapter này bằng khóa ORS. Không dùng tuyến ô tô thay cho đi bộ; ORS không phản ánh chắc chắn cửa khóa/chướng ngại tức thời.

Rank dùng quãng đường đi bộ chỉ khi tất cả kết quả đều có tuyến; nếu không thì dùng đường chim bay nhất quán và ghi phương pháp. Không trộn hai loại khoảng cách trong một thứ tự. Rating chỉ làm tiêu chí phụ khi đã có nguồn; không phải tổng hợp chất lượng khách quan. Không suy độ an toàn/thành phần dị ứng từ tên món.

## Kiểm thử

Tests giả lập gồm: Overpass timeout/rỗng/partial → Photon, Kakao FD6/GPS/bán kính, Unicode Hangul, lọc vòng tròn và quốc gia, thiếu key, giá/policy thiếu hoặc cũ, hai suất so với hai khách, phụ phí, minimum bill, sức chứa set, lịch mở cửa không phải open_now, ảnh URL không hợp lệ, ORS lỗi và xếp hạng quán chưa đủ bằng chứng. GitHub Actions chạy toàn bộ tests và Docker build; fixtures không được phục vụ như menu thật.

## Nguồn công khai đã bổ sung

Xem [MENU_SOURCES.md](MENU_SOURCES.md). Có 5 hồ sơ thật/15 mục menu ban đầu, công cụ `get_restaurant_sources`, làm mới từ Suwon/KTO và adapter JSON-LD cho website quán đã duyệt. Tập giá này chưa xác minh hiện tại tại quán và không tự tạo OSM/Kakao binding. Điều kiện tối thiểu theo người và theo suất được giữ riêng; không biến bài cũ thành quy định hiện tại.
