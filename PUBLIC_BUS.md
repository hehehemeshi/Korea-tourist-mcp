# Bus theo khu vực — 0.5.2

`search_bus_routes` không mặc định thành phố/tỉnh. Thứ tự chọn vùng: `region` người dùng hỏi → tọa độ WGS84 do ChatGPT truyền vào và reverse geocode Photon → hỏi lại. MCP không lấy GPS thiết bị. Khi không xác định được vùng, trả `needs_region`; thành phố chưa tích hợp trả `unsupported_region`, không dùng Seoul/Gyeonggi thay thế. Gwangju (광주) cần phân biệt thành phố trực thuộc trung ương với 광주시 thuộc Gyeonggi. Một địa điểm đích được hỏi rõ có ưu tiên hơn vị trí hiện tại.

Nguồn đã kiểm chứng bằng trình duyệt và HTTP không có cookie/key:

- **Seoul:** trang công khai https://bus.go.kr, các yêu cầu `/sbus/bus/selectVApiTotalstr.do`, `selectRouteInfo.do`, `selectBusposInfo.do`. Kiểm tra tuyến mẫu 143 (`100100022`) có 113 bến, 1.896 điểm đường và 26 bản ghi xe tại 2026-10-27 23:26 KST. Đây là quan sát kiểm tra, không phải dữ liệu live được đóng gói.
- **GBIS:** https://m.gbis.go.kr/search và các endpoint `/api/routeSearch`, `/api/routeDetail`, `/api/routeStations`, `/api/busRouteLine`, `/api/busLocationsOfRoute` đã kiểm chứng ở bản 0.5.1. Lọc đúng thành phố thuộc Gyeonggi được hỏi; hỏi cả tỉnh Gyeonggi sẽ lọc theo các thành phố tỉnh đó. Kết quả Incheon chỉ là phần GBIS liệt kê, có cảnh báo chưa tích hợp nguồn địa phương đầy đủ.

Seoul ưu tiên nguồn Seoul. Nếu nguồn này chưa trả tuyến, GBIS chỉ được bổ sung tuyến được ghi nhận chạy qua Seoul, có nhãn **phạm vi một phần**, không quảng cáo thay thế toàn bộ bus Seoul. Các thành phố/province khác như Busan/Daegu/Jeju hiện trả chưa tích hợp. TAGO và nguồn địa phương là công việc tiếp theo, chưa được bật khi chưa xác minh truy cập/dữ liệu thật. `/api/bus/coverage` công bố nguồn và giới hạn; `nationwide_coverage=false`.

Mã tuyến mới có namespace: `seoul:100100022`, `gbis:200000060`. Không suy đoán nguồn từ số bus, không gộp hai mã khác nguồn chỉ vì cùng số. Link numeric cũ (`200000060`) giữ tương thích GBIS theo hợp đồng bản trước, không có nghĩa là mặc định vùng khi tìm mới.

Mức chính xác khác nhau:

- **Seoul:** lấy GPS từ `gpsX/gpsY`, thời điểm đo từ `dataTm` và hướng đến từ `adirection`. Chỉ vẽ marker GPS xanh khi tọa độ hợp lệ và thời điểm đo còn trong 120 giây (cho phép lệch đồng hồ tương lai tối đa 30 giây). Bản ghi cũ/thiếu giờ/tương lai bất hợp lệ vẫn được ghi nhãn, không vẽ như vị trí xe trực tiếp. Không dùng thời điểm tải để làm mới GPS cũ. Không suy đoán góc hướng xe hoặc nội suy chuyển động.
- **GBIS:** dữ liệu đã kiểm chứng tham chiếu bến/thứ tự/trạng thái, không có GPS/thời điểm đo từng xe. Marker vàng neo vào bến tham chiếu, có nhãn rõ; thời điểm yêu cầu không phải thời điểm GPS.

Giao diện `/bus` không chọn sẵn vùng. Khi tìm vùng khác/không hỗ trợ, bản đồ cũ được ẩn, tránh hiện lại tuyến vùng trước như kết quả mới. Cả hai nguồn dùng schema bản đồ/bến/xe thống nhất, giữ nguồn/trạng thái/thời điểm từng phần. Hình học nguồn lỗi không được thay bằng đường nối các bến. Bản đồ dùng OSM có ghi công; chỉ tải ô đang xem. Metadata MCP Apps giữ hình học đầy đủ trong `_meta.busSnapshot`, không phình context LLM. Client không hỗ trợ widget có link trang cùng server tự lấy đúng route ID.

Các yêu cầu public-web này không phải developer API có cam kết ổn định. Không lấy khóa trong JavaScript, không đăng nhập/giả danh. Khi schema hoặc nguồn thay đổi, báo lỗi từng phần. Xe cache 15 giây, dữ liệu tĩnh tối đa 5 phút, giới hạn số mục và tối đa một lần thử lại cho lỗi mạng tạm thời. REST bus công khai khi `MCP_PUBLIC=true`, chế độ riêng giữ token; xác thực API cũ giữ nguyên. Không cần key data.go.kr cho hai nguồn hiện tại.

Hai công cụ này tìm/xem tuyến, chưa phải bộ định tuyến hành trình A→B nhiều chặng bus/tàu. Không có dữ liệu sân ga xác minh. Các công cụ tàu/nhà hàng cũ được giữ. Sau triển khai, `/healthz` báo 0.5.2; Refresh/Scan Tools để nhận tham số tọa độ tùy chọn và mô tả nguồn theo vùng. Không tuyên bố đã hỗ trợ toàn Hàn Quốc.
