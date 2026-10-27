# Nguồn menu, giá và điều kiện gọi món

Phiên bản 0.4.0 thêm `get_restaurant_sources` và kết nối nó với hai công cụ menu/policy hiện có. Dùng được khi chưa có API key. Không cần thay URL MCP; Refresh/Scan Tools sau khi deploy để thấy 19 công cụ.

## Dùng ngay

1. Gọi `get_restaurant_sources(query="Suwon")` hoặc chọn **Nguồn menu và giá** trên website. Có thể tìm bằng tên Hàn, Anh hoặc khu vực.
2. Lấy `restaurant_id` dạng `source:...` từ kết quả.
3. Gọi `get_restaurant_menu(restaurant_id=...)` và `get_order_policy(restaurant_id=...)`. Kiểm tra `source`, `published_on`, `discovery_method`, `refresh_status`, thời điểm từng fact và `item_policies`.

Ví dụ `source:suwon-219569` có ba món được thành phố Suwon niêm yết; `source:kto-ohyeon-dongmun` có điều kiện tối thiểu 2 **suất** cho một món; `source:kto-hankookjib` có điều kiện tối thiểu 2 **người** cho một set. Không đổi một loại điều kiện thành loại còn lại.

## Tập nguồn ban đầu: 5 quán, 15 mục menu

| ID | Nguồn | Thông tin và giới hạn |
|---|---|---|
| source:suwon-219569 | [Suwon: 옛날손칼국수](https://www.suwon.go.kr/web/tour/cultureTour/cultureTourView.do?categoryCd=145&mstSeqNo=219569) | Tên món/giá trong danh sách giá hợp lý; có địa chỉ. Bản ban đầu lấy từ trích xuất chỉ mục của trang chính thức, do tải trực tiếp timeout. |
| source:suwon-1168802 | [Suwon: 찬솔김밥](https://www.suwon.go.kr/web/tour/cultureTour/cultureTourView.do?categoryCd=145&mstSeqNo=1168802) | Bốn mục giá từ trích xuất chỉ mục trang chính thức; chưa có địa chỉ xác minh trong catalog, không tự định vị hoặc gán vào chi nhánh khác. |
| source:kto-ohyeon-dongmun | [VISITKOREA: bài về cơm phần](https://english.visitkorea.or.kr/svc/contents/contentsView.do?vcontsId=189672) | Bài xuất bản 2024-02-13; ghi rõ món nào tối thiểu 2 suất. Không áp dụng quy định đó cho mọi món. |
| source:kto-hankookjib | [VISITKOREA: bibimbap Jeonju](https://english.visitkorea.or.kr/svc/contents/contentsView.do?vcontsId=221301) | Bài xuất bản 2025-02-20; set ghi tối thiểu 2 người. Chưa xác định giá set là tổng hay mỗi người, nên price_basis vẫn unknown. |
| source:kto-apple-house | [VISITKOREA: món ăn đường phố](https://english.visitkorea.or.kr/svc/contents/contentsView.do?vcontsId=184669) | Bài xuất bản 2023-12-04; món ghi 2 suất là mô tả khẩu phần, không phải bằng chứng phải gọi tối thiểu 2 suất. |

**Đây là giá được nguồn công bố, không phải giá hiện tại đã được xác minh tại quán.** Các fact trong tập ban đầu đều unverified. Năm cũ của bài không bị che bằng thời gian vừa truy vấn. `checked_at` là lúc kiểm tra trích dẫn; `source_updated_at` để null nếu không biết. `published_on` giữ ngày xuất bản bài. Bản dịch Việt là bản diễn giải có nhãn translation, chưa được quán xác nhận. Không có ảnh thực đơn được giả tạo hoặc gán ảnh món ăn thành ảnh menu.

Không dùng trích đoạn Google như bằng chứng verified. Hai hồ sơ Suwon công khai ghi `search_index_extract`; ba hồ sơ KTO dùng `direct_page_review`. Không khẳng định điều kiện gọi món ở các quán Suwon vì nguồn tìm được chưa nói rõ.

## Cách cập nhật tự động

- **Suwon:** tải đúng URL trong catalog, kiểm tra tên và địa chỉ (nếu đã biết), chỉ đọc dòng bảng `대표메뉴`, lấy giá KRW cố định có tên món. Không lấy số trong quảng cáo/JavaScript/boilerplate. Không đoán giá “từ”, khoảng giá, đơn vị theo người hoặc min-order.
- **VISITKOREA:** giữ những trích dẫn ngắn đã rà soát, kiểm tra tên/địa chỉ quán còn trong bài và câu trích dẫn còn hiện diện. Câu không còn trong trang giữ timestamp cũ và cảnh báo bản lịch sử; không tự lấy nội dung của một quán khác thay thế. Thông tin tự động vẫn unverified.
- **Website chính thức của quán (tùy chọn):** adapter `merchant_jsonld` hỗ trợ JSON-LD Restaurant + MenuItem + Offer giá KRW. Catalog phải ghi đúng tên, địa chỉ đường của chi nhánh và URL do quản trị viên duyệt. Trang có nhiều Restaurant hoặc địa chỉ khác sẽ bị từ chối. Không tự áp dụng giá chuỗi cho mọi cửa hàng.
- Policy JSON-LD chỉ đọc `additionalProperty` có tên rõ `minimum_servings`, `minimum_diners` ở từng món, hoặc các khóa policy hiện có ở Restaurant. Giá trị phải đúng kiểu; không suy từ description, “2-serving set”, cuisine hay tên món. Không đọc mập mờ từ review để biến thành quy định của quán.
- Ảnh chỉ thu link gốc nếu alt mô tả rõ bảng menu/giá; không tải, OCR hay tự xác nhận nội dung ảnh. Ảnh món ăn chung không được gắn nhãn là ảnh menu.

Website chỉ cung cấp ảnh hoặc JavaScript động có thể chưa đọc được giá. Naver/Kakao Local hiện không được dùng như nguồn menu hoặc policy đã xác minh; không vượt đăng nhập/captcha hay scrape app đặt hàng. Có thể bổ sung ảnh/trang quán đã rà soát vào registry theo RESTAURANTS.md.

## Khi một nguồn lỗi

Trả bản snapshot cùng `refresh_status=unavailable_snapshot_only`, không thay timestamp bằng thời gian thất bại. Tải thành công có `retrieved_at`; cache giữ thời điểm tải gốc. Các trường không đủ bằng chứng luôn unknown/unverified và không làm quán được khẳng định phù hợp ngân sách.

Nguồn HTML chỉ được tải theo URL có sẵn trong `restaurant_sources.json`, không nhận URL từ người gọi tool. Chỉ HTTPS cổng 443, không IP literal/địa chỉ nội bộ trong URL hoặc credentials; không follow redirect, không thực thi script. Giới hạn 2 MB, timeout, 2 giây giữa request, 100 request/ngày/tiến trình và cache 64 trang/1 giờ. Chạy một worker/replica; không có bot crawl hàng loạt.

## Liên kết với quán gần GPS

Catalog ID độc lập để tránh ghép nhầm quán trùng tên. Mặc định không có OSM/Kakao binding. Tên giống nhau chỉ trả `possible_menu_sources`, chưa merge dữ liệu. Quản trị viên có thể thêm ID OSM/Kakao chính xác vào `bindings` sau khi đối chiếu chi nhánh. Khi đã bind, tìm quán gần GPS sẽ tải nguồn tương ứng để bổ sung phần thiếu; dữ liệu registry đã được rà soát vẫn ưu tiên, tự động không nâng thành verified. Catalog hiện không có tọa độ tự bịa; không tuyên bố 5 hồ sơ đều nằm trong 500 m của bạn.

## Quản trị và kiểm thử

Catalog: `src/seoul_transit/data/restaurant_sources.json`, schema cùng thư mục. Có thể sửa trong trình duyệt GitHub. Để dùng file khác, đặt `RESTAURANT_SOURCE_CATALOG` và COPY file vào Docker image. Source snapshot dùng cùng schema evidence; registry kiểm tra thủ công vẫn ở `restaurant_evidence.json`.

Tests bao gồm tách minimum diners/servings, snapshot cũ khi nguồn lỗi, parse giá/tiền tệ, không ghép chi nhánh, kiểm soát URL, giữ policy unknown và phân biệt ảnh món/ảnh thực đơn. Không có khóa API mới bắt buộc.
