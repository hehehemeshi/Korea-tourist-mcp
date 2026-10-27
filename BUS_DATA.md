# Bus data foundation — kiểm tra dữ liệu trước giao diện

Phạm vi đầu: GBIS Gyeonggi, gồm dữ liệu tuyến có thể tìm theo khu vực Suwon. Module `buses.py` đọc 4 operation HTTPS chính thức: tìm tuyến, danh sách bến, hình học tuyến và vị trí xe theo bến. Dùng `DATA_GO_KR_KEY` đã có trong cấu hình dự án; chủ tài khoản phải đăng ký quyền cho đúng dịch vụ.

- Tìm số tuyến trả các `routeId` và tên vùng/điểm đầu-cuối; không tự chọn tuyến trùng số.
- Hình học từ `getBusRouteLineListv2`, sắp bằng `lineSeq`. Không thay bằng đường thẳng nối các bến khi nguồn hình học thiếu/sai.
- Bến từ `getBusRouteStationListv2`, giữ `stationSeq`, điểm quay đầu và tọa độ hợp lệ. Thứ tự bến cần để phân biệt bến xuất hiện nhiều lần.
- Vị trí từ `getBusLocationListv2` có `vehId`, `plateNo`, `stationId`, `stationSeq`, `stateCd`. Tài liệu operation này không công bố x/y hoặc thời gian GPS xe. Vì vậy trả `gps_coordinates=null`, `vehicle_observed_at=null`, `position_kind=provider_stop_reference`; không tạo chấm GPS hay animation xe.
- `queryTime` là thời điểm yêu cầu, không phải thời điểm đo vị trí từng xe. Không gắn nhãn GPS live chỉ vì request mới thành công. Không suy đoán chiều xe từ hai bản ghi.
- Lỗi xác thực/provider không trở thành danh sách xe rỗng thành công; mỗi phần giữ trạng thái riêng. Không xuất khóa hoặc URL có khóa ra kết quả.

Nguồn:

- https://www.gbis.go.kr/gbis2014/publicService.action?cmd=mBusRoute
- https://www.gbis.go.kr/gbis2014/publicService.action?cmd=mBusRouteStation
- https://www.gbis.go.kr/gbis2014/publicService.action?cmd=mBusRouteLine
- https://www.gbis.go.kr/gbis2014/publicService.action?cmd=mBusLocation

Trạng thái: có adapter và tests fixture; **chưa xác minh gọi API thật thành công, chưa có bản đồ xe thật**, vì chưa có service key được cấp quyền. Không phát hành dữ liệu fixture như bus thực tế. Bản giao diện LLM ở PR #4 vẫn chưa merge. Trước khi ghép UI cần kiểm tra nguồn thật trên một `routeId` được người dùng chọn, hình học/bến đúng và mức chính xác của vị trí xe được ghi rõ. Seoul/TAGO là nguồn cần đánh giá riêng, không được quảng cáo module này hỗ trợ toàn Hàn Quốc.
