# Output quán ăn cho ChatGPT

Bản 0.5.0 giữ nguyên các nguồn và công cụ giao thông. ChatGPT truyền tọa độ ngữ cảnh vào `search_nearby_restaurants` hoặc `rank_restaurants`; MCP không yêu cầu truy cập GPS thiết bị. Mặc định bán kính 500 m, tối đa 10 quán gần đến xa. Khoảng cách xếp thứ tự là đường chim bay; khoảng cách đi bộ chỉ có khi nguồn định tuyến trả dữ liệu.

Kết quả giữ nguyên bằng chứng `data` và thêm:

- `presentation.restaurants`: số thứ tự, tên, khoảng cách, địa chỉ, link đi bộ Google Maps; menu Hàn–Việt và giá KRW ngay trong từng thẻ; điểm review, số lượt và nhận xét có nguồn.
- `presentation.map`: GeoJSON gồm vị trí đầu vào và các quán đánh số trùng danh sách.
- `markdown`: câu trả lời dự phòng với menu hiển thị trực tiếp và link bản đồ chung.
- MCP Apps resource `ui://korea-tourist/restaurants-v1.html`: bản đồ tương tác và danh sách cho client hỗ trợ UI. Metadata tương thích ChatGPT cũng được gửi. Nếu client chưa hiển thị widget, dùng Markdown và link bản đồ chung.

Dữ liệu thiếu ghi đúng **Chưa có thông tin**. Không suy đoán review từ số sao. Nhận xét nổi bật chỉ dùng `review_highlights` có nguồn HTTPS, giữ trạng thái xác minh và thời điểm kiểm tra. Tên món phổ biến có thể dịch bằng từ điển nhỏ, được gắn nhãn bản dịch tên món; không phải xác nhận nguyên liệu hoặc dị ứng. Giá niêm yết cũ vẫn ghi chưa xác minh hiện tại. Bản nâng cấp output không tự bổ sung giá hoặc review chưa có trong nguồn.

Bản đồ dùng OpenStreetMap, chỉ tải ô bản đồ đang xem, có ghi công. Link bản đồ chung chứa tọa độ và tên quán trong URL fragment (không gửi tới server trong HTTP request); tránh chia sẻ link nếu không muốn chia sẻ vị trí. `PUBLIC_BASE_URL` tùy chọn đặt thành URL HTTPS của deployment nếu đổi tên dịch vụ. Google Maps là link chỉ đường, không phải kết quả tuyến đã được MCP xác minh.

Sau khi cập nhật GitHub: Render → Manual Deploy → Deploy latest commit nếu chưa bật auto-deploy. `/healthz` cần báo `version: 0.5.0`. Trong ChatGPT, Refresh/Scan Tools kết nối hiện có để nhận metadata bản đồ; không cần tạo MCP mới hay cung cấp vị trí cho Codex để sửa output. UI nhúng phụ thuộc khả năng hỗ trợ MCP Apps của client.
