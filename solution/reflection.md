# Báo cáo phản hồi (Reflection)

## 1. Các loại lỗi khó bắt nhất và nguyên nhân

Các lỗi khó phát hiện nhất là nhóm lỗi tinh vi (subtle faults) trong phase Private, điển hình là trôi dạt nhẹ ở embedding_drift, corpus_staleness và bất thường thời lượng ở lineage_run.

Nguyên nhân kỹ thuật:
- Giá trị đo lường của các lỗi này nằm hoàn toàn bên trong dải dao động tự nhiên của dữ liệu sạch lịch sử.
- Điển hình: centroid_shift của ca trôi dạt tinh vi (0.0289 - 0.0311) thấp hơn mức biến thiên tự nhiên sạch (lên tới 0.0387); tuổi tài liệu trung bình của ca lỗi (31.8 - 37.6 ngày) nằm dưới dải bình thường (37.5 - 41.0 ngày); thời lượng job dbt chỉ tăng nhẹ (4480 - 4740 ms) so với mức tối đa sạch (4805 ms).
- Nếu hạ ngưỡng để bắt các lỗi này, tỷ lệ báo động giả (FPR) sẽ tăng mạnh. Do trọng số phạt FPR rất nặng (-30 điểm), chiến lược tối ưu là duy trì ngưỡng an toàn để đảm bảo FPR = 0%, bảo vệ độ tin cậy vận hành thực tế.

## 2. Đánh đổi chi phí và độ bao phủ nếu có thêm lượt cải tiến

Nếu có thêm lượt cải tiến, giải pháp sẽ tập trung vào hai hướng:

- Phân tầng kiểm tra để tiết kiệm ngân sách: Tận dụng dữ liệu miễn phí sẵn có trong payload để sàng lọc sơ bộ trước khi gọi các công cụ tốn 2.0 credits như feature_drift hay embedding_drift. Việc này giúp đưa chi phí phase Public về dưới mức ngân sách 220 credits mà vẫn giữ nguyên TPR = 100%.
- Sử dụng ctx.state để theo dõi thống kê động: Dùng ctx.state (không tốn credits) để tính toán thống kê trung bình trượt (EWMA) trên dòng sự kiện thực tế. Điều này hỗ trợ phân biệt rõ hơn giữa xu hướng suy giảm chất lượng thực sự và dao động ngẫu nhiên ngắn hạn, thay vì chỉ dựa vào ngưỡng tĩnh từ ctx.baseline.
