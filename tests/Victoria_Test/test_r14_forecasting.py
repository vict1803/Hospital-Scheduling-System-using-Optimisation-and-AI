"""R14 - upload ED/ICU history, forecast, compare MAE with the last-week seasonal-naive baseline
Test names start with the TC ID in the test-case sheet. Shared helpers: common.py; fixtures: conftest.py."""
import pytest
from common import *


# R14  FORECASTING  (uploads, forecast, MAE vs last-week baseline)

def test_tc_r14_01_valid_ed_upload_is_accepted(admin, tmp_path):
    ok, msg, n, _ = upload(admin, "ED", ed_file(tmp_path, weekly_ed(6)))
    assert ok, msg
    if n is not None: assert n == 6 * 168 
    # EXPECTED: all 1,008 rows loaded


def test_tc_r14_02_ed_forecast_is_hourly_continuous_and_nonnegative(admin, tmp_path):
    values = weekly_ed(6)
    assert upload(admin, "ED", ed_file(tmp_path, values))[0]
    forecast(admin, "ED")
    rows = forecast_rows(admin)
    assert rows
    t = [datetime.strptime(a, HOURLY) for a, _ in rows]
    assert t[0] == START + timedelta(hours=len(values))              # starts right after the last record
    assert all(b - a == timedelta(hours=1) for a, b in zip(t, t[1:]))  # hourly, no gaps
    assert all(v >= 0 for _, v in rows)


def test_tc_r14_03_ed_mae_matches_seasonal_naive_baseline_and_verdict_is_consistent(admin, tmp_path):
    # 5 weeks; last week is exactly +2 vs the week before -> test set = last 20% = last week
    # -> baseline (same hour last week) is wrong by exactly 2 every hour -> EXPECTED baseline MAE = 2.0
    assert upload(admin, "ED", ed_file(tmp_path, weekly_ed(5, last_week_extra=2)))[0]
    forecast(admin, "ED")
    model, base = mae(admin)
    assert base == pytest.approx(2.0, abs=0.01)
    assert (admin.locator(S["better"]).first.get_attribute("data-better") == "true") == (model < base)


def test_tc_r14_04_ed_model_not_claimed_better_when_baseline_is_perfect(admin, tmp_path):
    assert upload(admin, "ED", ed_file(tmp_path, weekly_ed(6)))[0]    # repeats exactly -> baseline MAE 0
    forecast(admin, "ED")
    _, base = mae(admin)
    assert base == pytest.approx(0, abs=0.01)
    assert admin.locator(S["better"]).first.get_attribute("data-better") == "false"


def test_tc_r14_05_valid_icu_upload_is_accepted(admin, tmp_path):
    ok, msg, _, _ = upload(admin, "ICU", icu_file(tmp_path, weekly_icu(12)))
    assert ok, msg


def test_tc_r14_06_icu_forecast_is_daily_continuous_and_nonnegative(admin, tmp_path):
    values = weekly_icu(12)
    assert upload(admin, "ICU", icu_file(tmp_path, values))[0]
    forecast(admin, "ICU")
    rows = forecast_rows(admin)
    assert rows
    t = [datetime.strptime(a[:10], DAILY) for a, _ in rows]
    assert t[0] == START + timedelta(days=len(values))
    assert all(b - a == timedelta(days=1) for a, b in zip(t, t[1:]))
    assert all(v >= 0 for _, v in rows)


def test_tc_r14_07_icu_mae_matches_same_weekday_baseline_and_verdict_is_consistent(admin, tmp_path):
    # 5 weeks, last week +3 vs the week before -> EXPECTED baseline MAE = 3.0 beds/day
    assert upload(admin, "ICU", icu_file(tmp_path, weekly_icu(5, last_week_extra=3)))[0]
    forecast(admin, "ICU")
    model, base = mae(admin)
    assert base == pytest.approx(3.0, abs=0.01)
    assert (admin.locator(S["better"]).first.get_attribute("data-better") == "true") == (model < base)


def test_tc_r14_08_patient_identifier_columns_are_never_shown(admin, tmp_path):
    rows = [r + ["PATIENT-ID-7731", "Ali Bin Abu"] for r in hourly(weekly_ed(6))]
    p = write_csv(tmp_path / "id.csv", list(ED_COLS) + ["patient_id", "name"], rows)
    upload(admin, "ED", p)                           # accepted-and-stripped OR rejected are both fine
    assert "PATIENT-ID-7731" not in admin.content() and "Ali Bin Abu" not in admin.content()


def test_tc_r14_09_upload_without_timestamp_column_is_rejected(admin, tmp_path):
    for ward, p in (("ED", ed_file(tmp_path, weekly_ed(6), header=("oops", ED_COLS[1]))),
                    ("ICU", icu_file(tmp_path, weekly_icu(8), header=("oops", ICU_COLS[1])))):
        ok, msg, _, _ = upload(admin, ward, p)
        assert not ok and msg                        # EXPECTED: rejected with a message


def test_tc_r14_10_upload_without_count_column_is_rejected(admin, tmp_path):
    ok, msg, _, _ = upload(admin, "ED", ed_file(tmp_path, weekly_ed(6), header=(ED_COLS[0], "whatever")))
    assert not ok and msg


@pytest.mark.parametrize("bad", ["-3", "abc", ""], ids=["negative", "non-numeric", "blank"])
def test_tc_r14_11_to_13_negative_nonnumeric_or_blank_counts_are_rejected(admin, tmp_path, bad):
    rows = hourly(weekly_ed(6)); rows[100][1] = bad
    ok, msg, _, _ = upload(admin, "ED", write_csv(tmp_path / "x.csv", ED_COLS, rows))
    assert not ok and msg                            # EXPECTED: invalid data never reaches forecasting


def test_tc_r14_14_unparsable_timestamp_is_rejected(admin, tmp_path):
    rows = hourly(weekly_ed(6)); rows[10][0] = "not-a-date"
    ok, msg, _, _ = upload(admin, "ED", write_csv(tmp_path / "x.csv", ED_COLS, rows))
    assert not ok and msg


@pytest.mark.parametrize("name,content", [("data.txt", "hello"), ("data.pdf", "%PDF-1.4"), ("empty.csv", ""),
                                          ("header_only.csv", "timestamp,arrivals\n")])
def test_tc_r14_15_16_unsupported_empty_or_header_only_file_is_rejected(admin, tmp_path, name, content):
    p = tmp_path / name; p.write_text(content)
    ok, msg, _, _ = upload(admin, "ED", p)
    assert not ok and msg


def test_tc_r14_17_daily_icu_data_in_hourly_ed_upload_is_rejected_or_flagged(admin, tmp_path):
    ok, msg, _, warn = upload(admin, "ED", icu_file(tmp_path, weekly_icu(8)))
    assert (not ok) or warn


def test_tc_r14_18_staff_user_cannot_upload_dataset(staff, tmp_path):
    ok, _, _, _ = upload(staff, "ED", ed_file(tmp_path, weekly_ed(6)))
    assert not ok                                    # EXPECTED: blocked for non-admin


def test_tc_r14_19_exact_duplicate_row_is_counted_once(admin, tmp_path):
    rows = hourly(weekly_ed(6)); rows.insert(51, list(rows[50]))
    ok, msg, n, _ = upload(admin, "ED", write_csv(tmp_path / "x.csv", ED_COLS, rows))
    assert ok, msg
    if n is not None: assert n == 6 * 168            # EXPECTED: still 1,008 rows, not 1,009


def test_tc_r14_20_duplicate_timestamp_with_different_counts_is_not_silently_summed(admin, tmp_path):
    # TBC: the report does not say which rule applies; the minimum expectation is "not silently summed"
    rows = hourly(weekly_ed(6)); rows.insert(51, [rows[50][0], int(rows[50][1]) + 7])
    ok, msg, _, warn = upload(admin, "ED", write_csv(tmp_path / "x.csv", ED_COLS, rows))
    assert (not ok and msg) or warn


@pytest.mark.parametrize("gap", [1, 24])
def test_tc_r14_21_22_gap_of_1h_and_24h_is_filled_with_zero(admin, tmp_path, gap):
    rows = hourly(weekly_ed(6)); del rows[300:300 + gap]
    ok, msg, n, _ = upload(admin, "ED", write_csv(tmp_path / "x.csv", ED_COLS, rows))
    assert ok, msg
    if n is not None: assert n == 6 * 168            # EXPECTED: missing hours filled -> full 1,008 rows


@pytest.mark.parametrize("gap", [25, 72])
def test_tc_r14_23_24_gap_of_25h_and_72h_is_flagged_not_filled(admin, tmp_path, gap):
    rows = hourly(weekly_ed(6)); del rows[300:300 + gap]
    ok, msg, n, warn = upload(admin, "ED", write_csv(tmp_path / "x.csv", ED_COLS, rows))
    assert (not ok and msg) or warn                  # EXPECTED: flagged
    if ok and n is not None: assert n == 6 * 168 - gap   # and NOT silently filled with zeros


def test_tc_r14_25_26_minimum_history_accepted_and_one_hour_less_rejected(admin, tmp_path):
    full = weekly_ed(MIN_ED_HOURS // 168 + 1)
    ok, msg, _, _ = upload(admin, "ED", ed_file(tmp_path, full[:MIN_ED_HOURS], "min.csv"))
    assert ok, msg
    forecast(admin, "ED"); assert forecast_rows(admin)
    ok2, msg2, _, _ = upload(admin, "ED", ed_file(tmp_path, full[:MIN_ED_HOURS - 1], "short.csv"))
    if ok2:
        forecast(admin, "ED"); assert visible(admin, S["f_err"])     # 'insufficient history' message
    else:
        assert msg2


def test_tc_r14_27_icu_duplicate_date_is_counted_once(admin, tmp_path):
    rows = daily(weekly_icu(8)); rows.insert(11, list(rows[10]))
    ok, msg, n, _ = upload(admin, "ICU", write_csv(tmp_path / "x.csv", ICU_COLS, rows))
    assert ok, msg
    if n is not None: assert n == 56


def test_tc_r14_28_icu_zero_census_is_accepted(admin, tmp_path):
    v = weekly_icu(8); v[20] = 0
    ok, msg, _, _ = upload(admin, "ICU", icu_file(tmp_path, v))
    assert ok, msg                                   # 0 patients is a legitimate census


def test_tc_r14_29_single_record_gives_insufficient_data_message(admin, tmp_path):
    ok, msg, _, _ = upload(admin, "ED", ed_file(tmp_path, [5]))
    if ok:
        forecast(admin, "ED"); assert visible(admin, S["f_err"]) and not forecast_rows(admin)
    else:
        assert msg


@pytest.mark.parametrize("ward", ["ED", "ICU"])
def test_tc_r14_30_31_all_zero_history_gives_zero_forecast_without_error(admin, tmp_path, ward):
    p = ed_file(tmp_path, [0] * 1008) if ward == "ED" else icu_file(tmp_path, [0] * 56)
    assert upload(admin, ward, p)[0]
    forecast(admin, ward)
    rows = forecast_rows(admin)
    assert rows and all(v == pytest.approx(0, abs=1e-6) for _, v in rows)   # EXPECTED: all zeros
    assert mae(admin) == (pytest.approx(0, abs=0.01), pytest.approx(0, abs=0.01))


def test_tc_r14_32_unsorted_rows_are_sorted_before_forecasting(admin, tmp_path):
    rows = hourly(weekly_ed(6)); rows.reverse()
    assert upload(admin, "ED", write_csv(tmp_path / "x.csv", ED_COLS, rows))[0]
    forecast(admin, "ED")
    assert datetime.strptime(forecast_rows(admin)[0][0], HOURLY) == START + timedelta(hours=1008)


def test_tc_r14_33_large_three_year_dataset_is_accepted(admin, tmp_path):
    ok, msg, _, _ = upload(admin, "ED", ed_file(tmp_path, weekly_ed(168)))      # ~28,000 hourly rows
    assert ok, msg
