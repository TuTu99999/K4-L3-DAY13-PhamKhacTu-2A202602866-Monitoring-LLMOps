# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

## 1. Thông tin học viên

- **Họ và tên:** Phạm Khắc Tú
- **MSSV:** 2A202602866
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/TuTu99999/K4-L3-DAY13-PhamKhacTu-2A202602866-Monitoring-LLMOps
- **Commit SHA cuối:** `1059adffb2731d30d33336c3362ab6d7aca1353c`
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602866`

## 2. Evidence index

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | [pytest.txt](evidence/pytest.txt) |
| Log validator | [log-validator.txt](evidence/log-validator.txt) |
| Dashboard validator | [dashboard-validator.txt](evidence/dashboard-validator.txt) |
| Ảnh kết quả pytest | [01-pytest.png](evidence/01-pytest.png) |
| Ảnh log validator | [02-log-validator.png](evidence/02-log-validator.png) |
| Ảnh dashboard validator | [03-dashboard-validator.png](evidence/03-dashboard-validator.png) |
| Structured log | [04-structured-log.png](evidence/04-structured-log.png) |
| PII redaction | [05-pii-redaction.png](evidence/05-pii-redaction.png) |
| Trace list | [06-trace-list.png](evidence/06-trace-list.png) |
| Trace waterfall | [07-trace-waterfall.png](evidence/07-trace-waterfall.png) |
| Trace metadata | [08-trace-metadata.png](evidence/08-trace-metadata.png) |
| Prompt v1 và v2 | [09 v1](evidence/09-prompt-versions_v1.png), [09 v2](evidence/09-prompt-versions_v2.png) |
| Promote và rollback prompt | [10 v1](evidence/10-prompt-rollback_v1.png), [10 v2](evidence/10-prompt-rollback_v2.png) |
| Dashboard overview | [11-dashboard-overview.png](evidence/11-dashboard-overview.png) |
| Incident metric | [12-incident-metric.png](evidence/12-incident-metric.png) |
| Incident log | [13-incident-log.png](evidence/13-incident-log.png) |
| Incident trace | [14-incident-trace.png](evidence/14-incident-trace.png) |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | khoảng 30/100 ở CP0 | 100/100 | Đạt đủ schema, correlation ID, enrichment và PII scrubbing |
| `validate_dashboard.py` | Chưa có dashboard runtime | 6/6 panel | Đúng dashboard contract |
| `pytest` | Chưa ghi lại số baseline | 27 passed | Không còn test lỗi |
| Số traces hợp lệ | 10 trace từ lượt load baseline | Ít nhất 24 root trace trong project cá nhân | Có đủ root/retrieval/generation |
| Số PII leak | Chưa đạt kiểm tra PII ở baseline | 0 | Validator và tests đều đạt |
| Latency P95 / TTFT P95 | 1888 ms / 50 ms (clean CP3) | 2659 ms / 50 ms (challenge) | P95 tăng 40.8% do retrieval chậm |
| Retrieval success rate | 100% | 100% | Incident làm chậm retrieval nhưng không làm retrieval lỗi |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** middleware gọi `clear_contextvars()` đầu mỗi request, nhận `x-request-id` nếu client gửi hoặc sinh `req-` cộng 8 ký tự hex. ID được bind vào structlog context, lưu ở `request.state`, dùng trong trace và trả lại qua header `x-request-id`; response đồng thời có `x-response-time-ms`.
- **Các metadata được ghi vào structured log:** `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`, `env`, `service`, `event`, timestamp; event phản hồi còn có latency, TTFT, token input/output, cost, quality, tool name và tool success.
- **Cách bảo đảm PII được scrub trước khi ghi:** chỉ lưu hash 12 ký tự của user ID và preview đã sanitize. Processor `scrub_event` chạy trước `JsonlFileProcessor`/JSON renderer, thay email, số điện thoại Việt Nam, CCCD và thẻ thanh toán bằng marker `[REDACTED_*]`.
- **Cách kiểm chứng kết quả:** `log-validator.txt` đạt 100/100, báo 0 potential PII leak; `pytest.txt` có 27 test pass, gồm test riêng cho CCCD và thẻ.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** mở project `day13-k4-l3b-2A202602866`, lọc thời gian chạy lab và kiểm tra trace name `day13-agent-request`, session, tag `lab`, feature và model do ứng dụng gửi.
- **Cấu trúc root/retrieval/generation observations:** root `lab-agent-run` kiểu agent bao bọc span `retrieval` kiểu retriever và span `generation` kiểu generation. Raw input/output không được tự động capture; chỉ metadata/preview an toàn được gửi.
- **Cách nối trace với log:** cùng một `correlation_id` được ghi trong JSON log và metadata của root trace; ví dụ incident dùng `req-7013f2fa` ở cả hai nơi.
- **Prompt name:** `day13-chat`.
- **Version/label baseline:** v1 mang label `baseline`; sau rollback v1 mang thêm `production`.
- **Version/label candidate:** v2 mang label `candidate` và `latest`; từng được promote thành `production` để tạo trace kiểm chứng.
- **Trace ID của mỗi version:** v1 baseline `330ec75a6cb64d7418e67c695d2b593c`; v2 candidate/production `4825d8fa16f777155df2fb3ce3d59ed3`; trace sau rollback về v1 `a7ac4bd6d056ab17e5dd5c865a075bd2`.
- **Cách promote và rollback `production`:** gắn label `production` cho v2, chạy request và xác nhận trace dùng v2; sau đó chuyển label `production` về v1 và chạy lại để xác nhận ứng dụng lấy đúng prompt rollback.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** dashboard local đọc `data/logs.jsonl` trong cửa sổ 60 phút, refresh 30 giây, gồm latency/TTFT, traffic, error/retrieval success, cost, input-output tokens và quality proxy. Mỗi panel có đơn vị cùng đường threshold; khi có challenge, banner so sánh P95 baseline và incident.
- **SLO và lý do chọn:** SLO chính là 99.5% request trong 28 ngày kết thúc bằng `response_sent` và có `latency_ms <= 3000`. Baseline nằm dưới ngưỡng này, còn ngưỡng vẫn đủ nhạy để phát hiện retrieval chậm kéo dài mà không cảnh báo vì dao động nhỏ của máy lab.
- **Cách tính error budget:** target 99.5% cho phép 0.5% bad request. Với 10,000 request trong cửa sổ 28 ngày, budget là `10,000 × 0.5% = 50` request lỗi hoặc chậm hơn 3000 ms.
- **Ba alert và runbook tương ứng:** `HighLatencyP95` khi P95 > 3000 ms trong 5 phút; `HighErrorRate` khi error rate > 2% trong 5 phút; `LowRetrievalSuccess` khi retrieval success < 90% trong 5 phút. Điều kiện, ảnh hưởng, ba bước kiểm tra và mitigation nằm trong `docs/alerts.md`.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`.
- **Khoảng thời gian điều tra:** 04:55:34–04:55:45 UTC ngày 30/09/2026; request đại diện chạy từ 04:55:40 đến 04:55:42 UTC.
- **Triệu chứng từ metrics:** latency P95 phía server tăng từ 1888 ms ở 10 request baseline lên 2659 ms ở 5 request challenge, tăng 40.8%. TTFT P95 vẫn 50 ms, error rate vẫn 0%, nên dấu hiệu tập trung ở một bước trước generation chứ không phải lỗi HTTP hay thời gian sinh token đầu tiên.
- **Log line và correlation ID liên quan:** event `response_sent` lúc `2026-09-30T04:55:42.909632Z`, `correlation_id=req-7013f2fa`, `session_id=k4-l3b-challenge-s01`, `feature=monitoring`, `latency_ms=2659`, `ttft_ms=50`, `tool_success=true`.
- **Trace ID và span gây ảnh hưởng:** trace `3b1ab112912f7d71a5190135758ce6fe` có root `lab-agent-run` 2661 ms; span `retrieval` 2501 ms trong khi span `generation` chỉ 152 ms. Trace dùng cùng `correlation_id=req-7013f2fa` với log.
- **Root cause:** incident `rag_slow` làm retrieval chậm khoảng 2.5 giây; retrieval chiếm gần toàn bộ thời gian root span, còn generation, token/cost và trạng thái request vẫn bình thường.
- **Fix action:** vô hiệu hóa `rag_slow`, xác nhận `/health` cho thấy cả `rag_slow`, `tool_fail`, `cost_spike` đều `false`; trong môi trường thật cần kiểm tra độ trễ/kết nối vector store và tạm dùng retrieval fallback hoặc giảm tải trong lúc khôi phục.
- **Preventive measure:** duy trì alert `HighLatencyP95`, drill-down log theo `correlation_id`, alert/metric riêng cho latency của span retrieval, đặt timeout/circuit breaker và kiểm thử hiệu năng retrieval định kỳ để phát hiện sớm trước khi ảnh hưởng P95 toàn hệ thống.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** tắt capture raw input/output trên cả root, retrieval và generation, chỉ gửi preview đã scrub cùng metadata cần vận hành. Cách này vẫn cho phép điều tra theo correlation ID nhưng giảm nguy cơ đưa PII lên log hoặc Langfuse.
- **Một lỗi/blocker đã gặp:** một tiến trình dashboard cũ giữ port 8501 nên bản dashboard mới không thể bind và giao diện vẫn hiển thị dữ liệu cũ.
- **Cách tìm nguyên nhân và xử lý:** kiểm tra port bằng `netstat`, xác định đúng PID Python giữ port, dừng riêng tiến trình đó rồi khởi động lại dashboard và kiểm tra `/api/dashboard` đã có incident comparison.
- **Cách hiểu luồng Metrics → Logs → Traces:** metrics cho biết latency P95 tăng và khoảng thời gian xảy ra; log trong khoảng đó cung cấp request đại diện cùng `correlation_id`; trace cùng ID phân rã tổng latency theo span và chỉ ra retrieval chiếm 2501/2661 ms.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** prompt version giúp biết chính xác cấu hình tạo ra response và cho phép rollback nhanh; token/cost phát hiện output bất thường; SLO biến trải nghiệm người dùng thành ngưỡng đo được; trace giúp quyết định rollback prompt hay xử lý dependency retrieval thay vì đoán.
- **Điều quan trọng nhất đã học:** một metric chỉ cho biết triệu chứng; cần correlation ID để nối metric với log và trace rồi mới kết luận root cause bằng span cụ thể.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** không còn hạn chế kỹ thuật; logging, PII protection, tracing, prompt versioning, dashboard, SLO/alerts và điều tra incident đều đã hoàn thành. Phần thủ tục còn lại là tạo commit cuối, cập nhật SHA và nộp URL/SHA trên LMS/Codelabs.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit nộp bài cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Có đúng 3 file text và 5 ảnh runtime theo hướng dẫn.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
