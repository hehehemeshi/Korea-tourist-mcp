# Đồng hành — hỏi đáp, bus/tàu và GPS ở Hàn Quốc

Bản 0.6.0 thêm trang di động tại `/` và `/companion`. Bộ công cụ trước đây giữ ở `/tools`; MCP `/mcp` và công cụ nhà hàng/tàu giữ nguyên. Không cần máy tính: mã được cập nhật qua GitHub, Render triển khai cùng dịch vụ hiện tại.

## Đã triển khai trong mã

- Chat tiếng Việt qua OpenAI, trích điểm đi/đến và ưu tiên ít đổi tuyến/ít đi bộ; hỏi lại khi thiếu dữ liệu. LLM không phải nguồn tạo tuyến, số bus hoặc sân ga. Hành trình lấy qua Google Routes TRANSIT, gồm đi bộ/bus/tàu theo phạm vi nhà cung cấp.
- Tối đa 3 hành trình, danh sách từng chặng, tên điểm lên/xuống, đầu xe/hướng tàu, số điểm dừng và giờ theo kế hoạch nếu API trả về. Trường thiếu ghi Chưa có thông tin; sân ga luôn unknown. Không bảo đảm đủ mọi tuyến KORAIL hoặc mọi vùng Hàn Quốc.
- Vẽ hình học do API trả về lên Google Maps, tô chặng được chọn. Không vẽ tuyến Google trên OpenStreetMap. Nếu thiếu khóa bản đồ, vẫn có danh sách chặng và link Google; bản đồ OSM dự phòng chỉ hiện GPS.
- `watchPosition` chỉ sau khi người dùng bấm bật. Nhắc gần cuối chặng khi có ít nhất 2 GPS fix đủ rõ qua ít nhất 2 giây; cảnh báo có thể lệch tuyến khi lệch hình học qua ít nhất 10 giây. Sai số trên 60 m, dữ liệu cũ trên 20 giây hoặc mất tín hiệu sẽ ngừng nhắc và ẩn chấm vị trí. Không suy đoán bằng thời gian.
- Người dùng chọn/xác nhận chặng; GPS không xác minh đã lên đúng xe. Nút xác nhận đến nơi dừng GPS. Cảnh báo cho phép chủ động tra cứu lại từ GPS mới; không tự gửi lại hoặc âm thầm đổi hành trình.
- Nhắc bằng hiển thị/vibration khi trình duyệt hỗ trợ. Thử giữ màn hình sáng bằng Wake Lock khi có; không bảo đảm nhắc khi chạy nền/khóa màn hình. Không phải dịch vụ thông báo nền.

## Cấu hình trên Render bằng điện thoại

Sau khi merge và Render Deploy latest commit, `/healthz` phải báo `0.6.0`.

1. Giữ `ACCESS_TOKEN` đang có. Trong trang, bấm ⚙ và nhập giá trị đó. Chỉ lưu trong sessionStorage của tab. Không chia sẻ token ở cuộc trò chuyện.
2. Thêm `GOOGLE_ROUTES_API_KEY`: tạo Google Cloud project, bật Routes API, cấu hình billing, quota và giới hạn API của khóa server. Không đưa khóa này vào HTML. [Google: Transit routes](https://developers.google.com/maps/documentation/routes/transit-route).
3. Thêm `GOOGLE_MAPS_BROWSER_KEY`: khóa riêng cho Maps JavaScript API, giới hạn HTTP referrer đúng domain Render của bạn, chỉ cho Maps JavaScript API. Đây là khóa publishable mà trình duyệt phải nhận; không dùng chung khóa server. [Bảo vệ khóa](https://developers.google.com/maps/api-security-best-practices).
4. Thêm `OPENAI_API_KEY` và tùy chọn `OPENAI_MODEL` (mặc định `gpt-4.1-mini`, cần model hỗ trợ Structured Outputs). Dùng khóa API từ tài khoản OpenAI Platform; gói ChatGPT không tự cấp API cho website. Khóa giữ phía server. Cấu hình hạn mức chi phí tại nhà cung cấp.
5. Lưu/redeploy, mở trang và kiểm tra trạng thái trong ⚙. Chưa có các khóa thì chỉ GPS/bản đồ OSM tại vị trí được cấp quyền hoạt động; trang không giả lập LLM hay tuyến.

Không thể phát hành sẵn các khóa Google/OpenAI thay chủ tài khoản. Việc có code và CI thành công không xác minh khóa, quota, dữ liệu địa phương hoặc GPS thật trên điện thoại.

## API và dữ liệu

`GET /api/journey/status`, `POST /api/journey/plan`, `POST /api/journey/chat`: dùng Bearer ACCESS_TOKEN. Không thêm LLM trả phí vào MCP công khai. Thiếu ACCESS_TOKEN phía server sẽ khóa các hành động trả phí ngay cả khi chưa bật middleware auth. POST kiểm tra Origin; các kết quả không cache qua HTTP. Không log URL truy vấn trong Docker command.

GPS liên tục xử lý trên thiết bị. Chỉ gửi tọa độ khi người dùng chọn dùng GPS cho tra cứu/chat hoặc bấm tra cứu lại từ đây. Chat chuyển điểm đi/đến, tối đa 10 tin gần nhất và dữ liệu tuyến đến OpenAI. Không lưu hội thoại vào database. Server giữ truy vấn người dùng tối đa 15 phút trong bộ nhớ, không lưu kết quả Google; hỏi tiếp sẽ đọc lại nguồn trước khi gửi context tuyến cho LLM. Reload/xóa phiên làm mất hội thoại; request đã gửi có thể vẫn hoàn tất ở provider. Phiên riêng trên tab không phải account isolation cho deployment nhiều người; deployment hiện thiết kế cho chủ ACCESS_TOKEN.

Google attribution giữ nguyên trên map; danh sách có attribution riêng. Trang có `/privacy` và `/terms`, tham chiếu các chính sách Google. [Google Routes policies](https://developers.google.com/maps/documentation/routes/policies).

## Kiểm tra

Python tests dùng provider fixtures chỉ trong test, kiểm tra API keys vắng mặt, tọa độ ngoài phạm vi, auth/Origin, provider facts, không suy đoán sân ga và LLM không thay thế tuyến. Node tests kiểm tra GPS yếu/cũ/trùng, nhắc gần điểm xuống và lệch tuyến cần tín hiệu liên tục. Không có tọa độ hoặc tuyến mẫu được phát hành như vị trí/hành trình thực của người dùng.
