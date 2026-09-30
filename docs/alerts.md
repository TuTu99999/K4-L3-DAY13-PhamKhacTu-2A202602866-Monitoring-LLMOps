# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của request thành công.
- Điều kiện và thời gian duy trì: `p95(response_sent.latency_ms) > 3000ms` liên tục 5 phút.
- Ảnh hưởng tới người dùng: phần đuôi request phản hồi chậm hơn mục tiêu SLO.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Latency để xác nhận P95/P99, TTFT và khoảng thời gian tăng.
  2. Lọc `response_sent` có `latency_ms > 3000`, lấy một `correlation_id` đại diện.
  3. Mở trace cùng ID và so sánh thời gian span `retrieval` với `generation`.
- Mitigation tạm thời: tắt incident practice nếu đang bật; nếu generation tăng sau đổi prompt thì rollback label `production`; nếu retrieval chậm thì giảm tải và kiểm tra vector store.
- Owner: `student-2A202602866`

## Alert 2

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: error rate tối đa 2%.
- Điều kiện và thời gian duy trì: `request_failed / request_received * 100 > 2%` liên tục 5 phút.
- Ảnh hưởng tới người dùng: request trả lỗi thay vì câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors để xác nhận error rate và breakdown theo `error_type`.
  2. Lọc `request_failed`, lấy `correlation_id`, `error_type` và `tool_name`.
  3. Mở trace cùng ID, tìm observation có trạng thái lỗi và status message tương ứng.
- Mitigation tạm thời: vô hiệu hóa scenario gây lỗi; khôi phục dependency retrieval; dùng fallback an toàn nếu upstream chưa phục hồi.
- Owner: `student-2A202602866`

## Alert 3

- Tên: `LowRetrievalSuccess`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: retrieval success tối thiểu 90%.
- Điều kiện và thời gian duy trì: tỷ lệ `tool_success=true` trên mọi event có `tool_success` nhỏ hơn 90% liên tục 5 phút.
- Ảnh hưởng tới người dùng: hệ thống không lấy được context, dễ trả lời thiếu căn cứ hoặc trả lỗi.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors và xác nhận retrieval success giảm, không chỉ nhìn tổng error rate.
  2. Lọc event có `tool_success=false`, lấy một `correlation_id` và thông tin lỗi.
  3. Mở trace cùng ID, kiểm tra observation `retrieval` và các bước sau nó.
- Mitigation tạm thời: tắt incident `tool_fail`, kiểm tra kết nối vector store và chuyển sang fallback document đã kiểm soát trong thời gian khôi phục.
- Owner: `student-2A202602866`
