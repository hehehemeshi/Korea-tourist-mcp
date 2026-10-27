# Thêm MCP vào ChatGPT

Mục tiêu: hỏi bằng tiếng Việt ngay trong ChatGPT; không cần dùng giao diện web riêng.

## Cần có

- Máy chủ MCP đang chạy trên HTTPS, ví dụ `https://TEN.onrender.com/mcp`.
- Tài khoản/workspace ChatGPT cho phép thêm MCP tùy chỉnh. Các mục menu tùy phiên bản và quyền quản trị.
- Khóa API ở máy chủ; không đưa khóa Seoul/Kakao/Naver vào lời nhắn ChatGPT.

GitHub Actions chỉ build/test hoặc kích hoạt deploy. Nó không phải hosting lâu dài. GITHUB_TOKEN của workflow tự được GitHub tạo, không cần gửi personal access token cho người hỗ trợ.

## Triển khai bằng trình duyệt

1. Đưa mã nguồn này vào repository GitHub; dùng GitHub Codespaces nếu cần thao tác file ẩn. Xem README để tạo Render Blueprint.
2. Trên Render cấu hình các khóa trong `.env.example`. KTO_API_KEY cần quyền EngService2; DATA_GO_KR_KEY cần quyền TAGO. Có thể dùng cùng giá trị nếu khóa đó đã được duyệt cả hai API. Kakao cần REST API key; Naver cần client ID và secret cho Maps.
3. Chọn xác thực:
   - Mặc định: MCP yêu cầu bearer ACCESS_TOKEN; dùng với client hỗ trợ header riêng.
   - Với ChatGPT có lựa chọn **No authentication**, đặt `MCP_PUBLIC=true`. Đây là endpoint công khai, chỉ đọc; ai biết URL cũng có thể gọi và tiêu thụ hạn mức API. ACCESS_TOKEN vẫn bảo vệ REST `/api/*`. Không gửi token trong URL. Dùng hosting có giới hạn request; production riêng tư nên triển khai OAuth gateway tương thích MCP. Mã hiện tại chưa triển khai OAuth.
4. Trong ChatGPT web tìm **Plugins → + → Add custom MCP server**, hoặc **Settings → Apps → Create** tùy giao diện. Dán URL HTTPS `/mcp`, chọn phương thức xác thực khớp bước 3, Scan Tools rồi Create. Nếu không thấy mục thêm MCP, kiểm tra quyền workspace/gói tài khoản theo tài liệu OpenAI.
5. Bật app vừa thêm trong cuộc trò chuyện. Kiểm tra có đủ 13 công cụ và thử: “Tìm điểm tham quan ở Seoul, tìm quán ăn bằng Kakao và tra tàu đến ga 강남; ghi nguồn và thời gian cập nhật.”

## Công cụ

Seoul/TAGO: search_stations, get_arrivals, plan_route, search_rail_stations, get_rail_schedule.
KTO: search_tourism, nearby_tourism, tourism_detail, search_festivals, search_stays.
Kakao: search_places.
Naver: geocode_address, get_driving_route.

Naver chỉ đường ô tô; không phải đường đi metro/xe buýt. plan_route cần đồ thị đã xác minh như README. Không công cụ nào đặt vé, gọi taxi hoặc đặt khách sạn. Số sân ga không có dữ liệu xác minh sẽ để trống. Nội dung KTO tiếng Anh và Kakao tiếng Hàn được giữ nguyên; ChatGPT có thể giải thích bằng tiếng Việt.

Tài liệu chính thức:
- https://developers.openai.com/api/docs/guides/custom-mcp-server
- https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt
