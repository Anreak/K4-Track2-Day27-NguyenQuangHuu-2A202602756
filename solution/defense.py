"""
Logic phòng thủ Data Siege bảo vệ pipeline dữ liệu.
Tuân thủ giao diện sandbox, cân bằng chi phí và độ chính xác.
"""
import math
from api import Verdict


def register(ctx):
    ctx.on("data_batch", check_data_batch)
    ctx.on("contract_checkpoint", check_contract_checkpoint)
    ctx.on("lineage_run", check_lineage_run)
    ctx.on("feature_materialization", check_feature_materialization)
    ctx.on("embedding_batch", check_embedding_batch)


def check_data_batch(payload, ctx):
    batch_id = payload.get("batch_id")
    prof = ctx.tools.batch_profile(batch_id)
    if not prof or "error" in prof:
        return Verdict(alert=False, pillar="checks")

    row_count = prof.get("row_count", 0)
    null_rate = prof.get("null_rate", {}).get("customer_id", 0.0)
    mean_amount = prof.get("mean_amount", 0.0)
    staleness_min = prof.get("staleness_min", 0.0)

    # 1. Kiểm tra ngưỡng đơn chiều với baseline 3 sigma
    if row_count < ctx.baseline.get("row_count_min", 435.4732) or row_count > ctx.baseline.get("row_count_max", 561.2948):
        return Verdict(alert=True, pillar="checks", reason="row_count_out_of_bounds")
    if null_rate > ctx.baseline.get("null_rate_max", 0.0109):
        return Verdict(alert=True, pillar="checks", reason="null_rate_spike")
    if mean_amount < ctx.baseline.get("mean_amount_min", 72.7645) or mean_amount > ctx.baseline.get("mean_amount_max", 90.6053):
        return Verdict(alert=True, pillar="checks", reason="mean_amount_out_of_bounds")
    if staleness_min > ctx.baseline.get("staleness_min_max", 8.418):
        return Verdict(alert=True, pillar="checks", reason="freshness_lag")

    # 2. Đánh giá bất thường đa chiều (Multi-signal Composite Distance)
    mu_rows = (ctx.baseline.get("row_count_min", 435.4732) + ctx.baseline.get("row_count_max", 561.2948)) / 2.0
    sigma_rows = (ctx.baseline.get("row_count_max", 561.2948) - ctx.baseline.get("row_count_min", 435.4732)) / 6.0
    mu_mean = (ctx.baseline.get("mean_amount_min", 72.7645) + ctx.baseline.get("mean_amount_max", 90.6053)) / 2.0
    sigma_mean = (ctx.baseline.get("mean_amount_max", 90.6053) - ctx.baseline.get("mean_amount_min", 72.7645)) / 6.0
    null_max = ctx.baseline.get("null_rate_max", 0.0109)
    stale_max = ctx.baseline.get("staleness_min_max", 8.418)

    r_norm = (row_count - mu_rows) / sigma_rows
    m_norm = (mean_amount - mu_mean) / sigma_mean
    n_norm = null_rate / null_max if null_max else 0.0
    s_norm = staleness_min / stale_max if stale_max else 0.0

    norm2 = math.sqrt(r_norm * r_norm + m_norm * m_norm + n_norm * n_norm + s_norm * s_norm)
    if norm2 > 3.2:
        return Verdict(alert=True, pillar="checks", reason="composite_distance_spike")

    return Verdict(alert=False, pillar="checks")


def check_contract_checkpoint(payload, ctx):
    contract_id = payload.get("contract_id")
    checkpoint_batch_id = payload.get("checkpoint_batch_id")
    diff = ctx.tools.contract_diff(contract_id, checkpoint_batch_id)
    if not diff or "error" in diff:
        return Verdict(alert=False, pillar="contracts")

    violations = diff.get("violations", [])
    if violations:
        return Verdict(alert=True, pillar="contracts", reason=f"violations_{','.join(violations)}")

    freshness_delay = diff.get("freshness_delay_min", 0.0)
    declared_sla = payload.get("declared_sla", {}).get("freshness_min", 15.0)
    baseline_sla = ctx.baseline.get("freshness_delay_max_min", 11.1141)

    if freshness_delay > declared_sla or freshness_delay > baseline_sla:
        return Verdict(alert=True, pillar="contracts", reason="sla_freshness_violation")

    return Verdict(alert=False, pillar="contracts")


def check_lineage_run(payload, ctx):
    run_id = payload.get("run_id")
    slice_data = ctx.tools.lineage_graph_slice(run_id)
    if not slice_data or "error" in slice_data:
        return Verdict(alert=False, pillar="lineage")

    downstream_cnt = slice_data.get("actual_downstream_count", 1)
    if downstream_cnt == 0:
        return Verdict(alert=True, pillar="lineage", reason="orphan_output")

    upstream = slice_data.get("actual_upstream", [])
    if "raw.orders" not in upstream or "raw.customers" not in upstream:
        return Verdict(alert=True, pillar="lineage", reason="missing_upstream")

    duration_ms = slice_data.get("duration_ms", 0.0)
    duration_max = ctx.baseline.get("lineage_duration_ms_max", 5134.9804)
    if duration_ms > duration_max:
        return Verdict(alert=True, pillar="lineage", reason="runtime_anomaly")

    return Verdict(alert=False, pillar="lineage")


def check_feature_materialization(payload, ctx):
    feature_view = payload.get("feature_view")
    batch_id = payload.get("batch_id")
    drift = ctx.tools.feature_drift(feature_view, batch_id)
    if not drift or "error" in drift:
        return Verdict(alert=False, pillar="ai_infra")

    mean_shift_sigma = drift.get("mean_shift_sigma")
    if mean_shift_sigma is None:
        serve_mean = drift.get("serve_mean", 0.0)
        train_mean = drift.get("train_mean", 0.0)
        train_std = drift.get("train_std", 1.0)
        mean_shift_sigma = abs(serve_mean - train_mean) / train_std if train_std else 0.0

    # Ngưỡng phân tách hiệu chuẩn an toàn giữa nhiễu tự nhiên sạch (<= 0.472) và trôi dạt lỗi (>= 0.970)
    if mean_shift_sigma > 0.65:
        return Verdict(alert=True, pillar="ai_infra", reason="feature_skew")

    return Verdict(alert=False, pillar="ai_infra")


def check_embedding_batch(payload, ctx):
    corpus = payload.get("corpus")
    chunk_batch_id = payload.get("chunk_batch_id")
    drift = ctx.tools.embedding_drift(corpus, chunk_batch_id)
    if not drift or "error" in drift:
        return Verdict(alert=False, pillar="ai_infra")

    centroid_shift = drift.get("centroid_shift", 0.0)
    if centroid_shift >= 0.0395:
        return Verdict(alert=True, pillar="ai_infra", reason="embedding_drift")

    avg_doc_age = drift.get("avg_doc_age_days", 0.0)
    if avg_doc_age > 42.0:
        return Verdict(alert=True, pillar="ai_infra", reason="corpus_staleness")

    return Verdict(alert=False, pillar="ai_infra")
