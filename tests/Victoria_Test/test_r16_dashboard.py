"""R16 - interactive dashboard: ward and date-period filters. ED day d total = 24*(d+1); ICU day d census = d+1
Test names start with the TC ID in the test-case sheet. Shared helpers: common.py; fixtures: conftest.py."""
import pytest
from common import *


# R16  DASHBOARD  (ED day d total = 24*(d+1); ICU day d census = d+1; data starts Mon 2026-01-05)

def test_tc_r16_01_dashboard_opens_with_chart_and_filters(loaded):
    loaded.goto(BASE_URL + URL["dashboard"])
    assert visible(loaded, S["d_chart"])
    assert all(loaded.locator(S[k]).first.is_visible() for k in ("d_ward", "d_from", "d_to"))


@pytest.mark.parametrize("ward", ["ED", "ICU"])
def test_tc_r16_02_03_ward_filter_shows_only_selected_ward_data(loaded, ward):
    set_filters(loaded, ward=ward)
    assert shown(loaded) == pytest.approx(EXPECTED_DAILY[ward])


@pytest.mark.parametrize("ward", ["ED", "ICU"])
def test_tc_r16_04_date_period_filter_shows_only_selected_days(loaded, ward):
    set_filters(loaded, ward, "2026-01-12", "2026-01-18")
    assert shown(loaded) == pytest.approx(between(ward, "2026-01-12", "2026-01-18"))   # 7 days


def test_tc_r16_05_ward_and_period_filters_work_together(loaded):
    set_filters(loaded, "ICU", "2026-01-20", "2026-02-02")
    assert shown(loaded) == pytest.approx(between("ICU", "2026-01-20", "2026-02-02"))
    set_filters(loaded, ward="ED")                   # change only the ward: period is kept
    assert shown(loaded) == pytest.approx(between("ED", "2026-01-20", "2026-02-02"))


def test_tc_r16_06_period_without_data_shows_empty_message(loaded):
    set_filters(loaded, "ED", "2025-01-01", "2025-01-07")
    assert visible(loaded, S["d_empty"])             # EXPECTED: clear "no data" message
    assert not visible(loaded, S["d_chart"], 800) or points(loaded) == []


def test_tc_r16_07_start_date_after_end_date_shows_message(loaded):
    set_filters(loaded, "ED", "2026-01-20", "2026-01-10")
    assert visible(loaded, S["d_err"]) or visible(loaded, S["d_empty"])


@pytest.mark.parametrize("ward", ["ED", "ICU"])
@pytest.mark.parametrize("day", ["2026-01-05", "2026-02-15", "2026-01-21"], ids=["first", "last", "middle"])
def test_tc_r16_08_to_10_single_day_first_last_and_middle_is_correct(loaded, ward, day):
    set_filters(loaded, ward, day, day)              # start date = end date
    assert shown(loaded) == pytest.approx({day: EXPECTED_DAILY[ward][day]})


def test_tc_r16_11_range_partly_outside_data_shows_available_days(loaded):
    set_filters(loaded, "ED", "2025-12-25", "2026-01-08")
    got = shown(loaded)
    for d, v in between("ED", "2026-01-05", "2026-01-08").items():
        assert got[d] == pytest.approx(v)
    assert not visible(loaded, S["d_err"], 800)


def test_tc_r16_12_ward_without_data_shows_message_other_ward_still_works(admin, tmp_path):
    assert upload(admin, "ED", ed_file(tmp_path, ED_DASH))[0]                # ICU never uploaded
    set_filters(admin, "ICU"); assert visible(admin, S["d_empty"])
    set_filters(admin, "ED"); assert shown(admin) == pytest.approx(EXPECTED_DAILY["ED"])
