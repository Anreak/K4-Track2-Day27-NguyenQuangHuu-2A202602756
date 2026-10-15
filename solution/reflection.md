# Báo cáo phản hồi (Reflection)

## Các loại lỗi khó bắt nhất và nguyên nhân

Những lỗi khó bắt nhất tập trung chủ yếu ở các trường hợp tinh vi (subtle faults) trong phase Private, bao gồm:
- Lỗi subtle embedding_drift và corpus_staleness trong luồng embedding_batch.
- Lỗi subtle volume_drop, volume_spike, null_spike trong luồng data_batch.
- Lỗi subtle runtime_anomaly trong luồng lineage_run.

Nguyên nhân:
Các mẫu dữ liệu bị lỗi này có giá trị đo lường nằm hoàn toàn bên trong dải dao động tự nhiên của dữ liệu sạch lịch sử. Cụ thể:
- centroid_shift của các ca trôi dạt tinh vi dao động từ 0.0289 đến 0.0311, trong khi dữ liệu sạch có độ lệch tự nhiên lên đến 0.0387.
- avg_doc_age_days của các ca corpus_staleness tinh vi là từ 31.8 đến 37.6 ngày, trong khi dữ liệu sạch có tuổi trung bình dao động từ 37.5 đến 41.0 ngày.
- runtime của dbt job trong lineage_run bị nghẽn nhẹ ở mức 4480 - 4740 ms, trong khi job bình thường có lúc chạy mất tới 4805 ms.

Nếu cố tình hạ ngưỡng phát hiện để bắt các ca lỗi này, hệ thống sẽ phát sinh hàng loạt báo động giả (False Positives) trên dòng sự kiện bình thường. Trong công thức chấm điểm, trọng số phạt của FPR lên tới -30 điểm (gấp nhiều lần mức đóng góp nhỏ của một vài lỗi riêng lẻ). Do đó, việc giữ vững ngưỡng phân tách an toàn để bảo toàn FPR = 0% là chiến lược tối ưu cả về điểm số kỹ thuật lẫn độ tin cậy trong vận hành thực tế.

## Thay đổi về đánh đổi chi phí và độ bao phủ nếu có thêm lượt cải tiến

1. Quản lý hạn mức thông minh ở phase Public:
Ở phase Public, tổng chi phí gọi công cụ là 240.0 credits trên ngân sách 220.0 credits (overage 0.0909, bị trừ 1.82 điểm). Tuy mất 1.82 điểm do vượt ngân sách nhẹ, việc gọi đủ công cụ giúp giải pháp đạt TPR tuyệt đối 100% (+50.0 điểm), mang lại điểm số tổng thể rất cao là 48.18 điểm. Nếu có thêm một lượt cải tiến, giải pháp có thể phân tầng sâu hơn bằng cách kiểm tra sơ bộ metadata trong payload miễn phí trước khi quyết định gọi các công cụ tốn kém như feature_drift và embedding_drift (2.0 credits mỗi lần).

2. Tận dụng ctx.state để xây dựng thống kê luồng động (Online Streaming Statistics):
Thay vì chỉ phụ thuộc vào các ngưỡng tĩnh từ ctx.baseline, ta có thể dùng ctx.state (hoàn toàn miễn phí credits) để tích lũy thống kê trung bình trượt (EWMA) và độ biến thiên thời gian thực trên chính luồng stream. Điều này giúp phát hiện các xu hướng trôi dạt từ từ theo chuỗi thời gian mà không gây báo động nhầm trên các nhiễu cục bộ ngắn hạn.
