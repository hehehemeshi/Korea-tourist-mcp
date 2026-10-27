# Thêm MCP du lịch Hàn Quốc vào ChatGPT

Mặc định dùng nguồn mở + link Google. Không cần khóa API du lịch để bắt đầu. Máy chủ vẫn phải được triển khai HTTPS; GitHub Actions chỉ build/test, không cung cấp hosting lâu dài.

1. Bấm [Deploy to Render](https://render.com/deploy?repo=https://github.com/hehehemeshi/Korea-tourist-mcp). Gói Free có thể ngủ và khởi động chậm.
2. Trong Render → Environment, chọn cách xác thực:
   - Mặc định yêu cầu bearer ACCESS_TOKEN; phù hợp client có thể gửi header Authorization.
   - Nếu ChatGPT chỉ có **No authentication**, đặt `MCP_PUBLIC=true` rồi lưu/redeploy. URL `/mcp` lúc này công khai, chỉ đọc, ai biết URL đều có thể gọi và sử dụng hạn mức truy vấn chung. `/api/*` vẫn cần ACCESS_TOKEN. Không đặt token trong URL. Muốn MCP riêng tư với ChatGPT cần OAuth gateway; dự án hiện chưa có OAuth.
3. Trong ChatGPT web: **Plugins → + → Add custom MCP server**, hoặc **Settings → Apps → Create** tùy giao diện và quyền tài khoản. Dán `https://TEN.onrender.com/mcp`, chọn xác thực tương ứng, Scan Tools rồi Create.
4. Bật app trong cuộc trò chuyện, thử: “Tìm ga Gangnam từ nguồn mở, ghi nguồn và tạo link Google Maps đi từ Seoul Station.”
5. Khi thay đổi bộ công cụ, dùng Refresh/Scan Tools trong phần quản lý kết nối để ChatGPT nhận công cụ mới.

Bạn sẽ thấy 14 công cụ. Dữ liệu OSM có thể thiếu hoặc khác dữ liệu cơ quan chính thức. Tên/địa chỉ dùng tiếng Anh hoặc Hàn; ChatGPT giải thích bằng tiếng Việt. Công cụ chỉ đường trả liên kết Google, không trả tuyến hay giờ tàu đã được đọc từ Google. Tàu trực tiếp, lịch TAGO và chi tiết KTO vẫn báo unavailable nếu chưa có khóa, không suy đoán số sân ga.

Nếu gặp 401, kiểm tra phương thức xác thực và MCP_PUBLIC. Nếu request timeout, mở `/healthz` để đánh thức máy chủ Free rồi thử lại. Nếu app chưa có dữ liệu tìm kiếm, kiểm tra truy vấn tiếng Anh/Hàn và xem link Google dự phòng. Nếu không có mục thêm MCP, kiểm tra gói và quyền workspace.

[Hướng dẫn OpenAI](https://developers.openai.com/api/docs/guides/custom-mcp-server)
