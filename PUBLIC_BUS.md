# Bus tự động, không cần key của data.go.kr

Bản 0.5.1 bổ sung `search_bus_routes` và `get_bus_route_map`, cùng trang `/bus`. ChatGPT tìm tuyến theo số/khu vực rồi lấy bản đồ ngay bằng công cụ; không yêu cầu người dùng mở GBIS và tìm lại thủ công. LLM sử dụng ChatGPT đang kết nối MCP, không thêm khóa LLM cho tính năng này.

Nguồn: các yêu cầu không đăng nhập của [GBIS mobile web](https://m.gbis.go.kr/search): `/api/routeSearch?keyword=…`, `/api/routeDetail?routeId=…`, `/api/routeStations?routeId=…`, `/api/busRouteLine?routeId=…`, `/api/busLocationsOfRoute?routeId=…`. Đã kiểm tra bằng trình duyệt thật và HTTP mới không có cookie/khóa trên GitHub Actions: tuyến mẫu 11 Suwon (`200000060`), 181 bến, hình học tuyến và các bản ghi xe. Số xe thay đổi theo lần đọc, không đóng gói kết quả đó làm dữ liệu live.

Đây là adapter của trang web công khai, **không phải developer OpenAPI có cam kết ổn định**. Không lấy khóa từ JavaScript, không dùng cookie đăng nhập hoặc giả danh tài khoản. Nếu nguồn thay đổi/không phản hồi, công cụ báo lỗi từng phần. API source cố định, không cho caller gửi URL. Có cache hạn chế: xe 15 giây, hình học/bến/thông tin tuyến 5 phút, tối đa 128 mục. Giữ thời điểm đọc từng phần. Không quét hàng loạt các tuyến.

Bản đồ dùng đường tuyến GBIS thật, bến theo thứ tự, dấu xe màu vàng **neo vào bến tham chiếu**. Dữ liệu xe quan sát được có `stationId`, `stationSeq`, `stateCd`, không có tọa độ GPS và thời điểm đo GPS từng xe. Không nội suy/animate xe, không đoán hướng, không coi `queryTime` là thời điểm GPS. Vị trí bản đồ xe là bến/đoạn tham chiếu, được gắn nhãn rõ. Chỉ coi là GPS xe nếu sau này có nguồn tọa độ được xác minh riêng.

Không lấy hình học bằng cách nối các bến khi nguồn hình học hỏng. Bến lặp trên hai chiều cần cả ID và thứ tự để gắn xe. Nguồn trả rỗng không xác nhận tuyến ngừng chạy; lỗi không được biến thành thành công rỗng. Gyeonggi/GBIS là phạm vi hiện tại; không quảng cáo đã bao phủ toàn Hàn Quốc hoặc đã tính được hành trình A→B bằng bus/tàu.

MCP Apps resource `ui://korea-tourist/bus-map-v1.html` hiển thị bản đồ ngay trong client hỗ trợ. Hình học đầy đủ gửi ở `_meta.busSnapshot` cho UI, không làm phình context LLM; dữ liệu tuyến/bến/xe giữ trong structured content. Client không hỗ trợ widget có link `/bus?route_id=…` cùng server, tự lấy đúng tuyến, không phải mở GBIS để tìm thủ công. Trang riêng cho phép nhập số tuyến/khu vực và cập nhật snapshot. Khi lỗi làm mới, dữ liệu trước được ghi rõ chưa cập nhật.

Hai REST API `/api/bus/search` và `/api/bus/route` công khai khi `MCP_PUBLIC=true`, giống hai công cụ MCP chỉ đọc. Với MCP riêng và ACCESS_TOKEN, API bus vẫn yêu cầu token; các REST API trước đây giữ xác thực. Không thêm khóa vào URL. Bản đồ OpenStreetMap ghi công và chỉ tải ô đang xem.

Deploy cùng dịch vụ Render hiện có. `/healthz` báo `0.5.1`; Refresh/Scan Tools một lần trong ChatGPT để nhận 2 công cụ mới (21 công cụ tổng). Thử: “Dùng search_bus_routes tìm bus 11 ở Suwon, sau đó get_bus_route_map và hiển thị bản đồ tuyến cùng xe theo bến, ghi nguồn/thời điểm.” Đây chưa phải tính năng tính tuyến nhiều chặng A→B hoặc báo GPS chính xác từng xe.
