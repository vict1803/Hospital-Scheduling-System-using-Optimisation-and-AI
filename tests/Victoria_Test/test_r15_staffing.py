"""R15 - ED and ICU staffing recommendations. ED = ceil(0.1A/5)+ceil(0.4A/10)+ceil(0.5A/25); ICU = ceil(census/4)
Test names start with the TC ID in the test-case sheet. Shared helpers: common.py; fixtures: conftest.py."""
import pytest
from common import *


# 
# R15  STAFFING  (expected doctors written out by hand from the report formulas)
#   ED  = ceil(0.1A/5) + ceil(0.4A/10) + ceil(0.5A/25)        ICU = ceil(census / 4)
# 
ED_EXPECTED = {100: 8, 250: 20, 1: 3, 25: 3, 26: 4, 50: 4, 51: 7, 75: 7, 76: 8, 101: 11, 251: 23}
ICU_EXPECTED = {20: 5, 10: 3, 1: 1, 4: 1, 5: 2, 8: 2, 9: 3}


@pytest.mark.parametrize("arrivals,doctors", ED_EXPECTED.items(), ids=[f"A={a}" for a in ED_EXPECTED])
def test_tc_r15_01_to_11_ed_doctors_match_triage_formula(admin, arrivals, doctors):
    assert staffing(admin, "ED", arrivals) == {"doctors": doctors}


def test_tc_r15_12_ed_zero_arrivals_gives_minimum_cover(admin):          # TBC: min cover not in the report
    assert staffing(admin, "ED", 0) == {"doctors": MIN_COVER_ED}


def test_tc_r15_13_ed_fractional_forecast_is_handled_consistently(admin):   # TBC: 11 (raw) or 8 (rounded first)
    assert staffing(admin, "ED", 100.5)["doctors"] in (11, 8)


@pytest.mark.parametrize("census,doctors", ICU_EXPECTED.items(), ids=[f"C={c}" for c in ICU_EXPECTED])
def test_tc_r15_14_to_20_icu_doctors_are_census_over_4_rounded_up(admin, census, doctors):
    assert staffing(admin, "ICU", census) == {"doctors": doctors}


def test_tc_r15_21_icu_zero_census_gives_minimum_cover(admin):           # TBC
    assert staffing(admin, "ICU", 0) == {"doctors": MIN_COVER_ICU}


@pytest.mark.parametrize("ward", ["ED", "ICU"])
@pytest.mark.parametrize("bad", ["-1", "-100", "abc", ""], ids=["neg1", "neg100", "text", "blank"])
def test_tc_r15_22_23_negative_nonnumeric_or_blank_forecast_is_rejected(admin, ward, bad):
    out = staffing(admin, ward, bad)
    assert out.get("error")                          # EXPECTED: rejected with a message


def test_tc_r15_24_ed_constant_demand_gives_correct_doctors_per_shift(admin, tmp_path):
    # 10 arrivals EVERY hour -> Pagi 07-14 (7h) = 70 -> 7 doctors; Petang 14-21 (7h) = 70 -> 7; Malam 21-08 (11h) = 110 -> 11
    assert upload(admin, "ED", ed_file(tmp_path, [10] * 1008))[0]
    forecast(admin, "ED")
    r = admin.locator(S["s_row"])
    assert r.count() > 0
    expected = {"pagi": (70, 7), "petang": (70, 7), "malam": (110, 11)}
    for i in range(r.count()):
        shift = r.nth(i).get_attribute("data-shift").lower()
        arrivals, doctors = expected[shift]
        assert float(r.nth(i).get_attribute("data-forecast")) == pytest.approx(arrivals, abs=1.0)
        assert int(r.nth(i).get_attribute("data-doctors")) == doctors


def test_tc_r15_25_icu_constant_census_gives_correct_doctors(admin, tmp_path):
    assert upload(admin, "ICU", icu_file(tmp_path, [18] * 56))[0]         # census 18 -> ceil(18/4) = 5
    forecast(admin, "ICU")
    r = admin.locator(S["s_row"])
    assert r.count() > 0 and all(int(r.nth(i).get_attribute("data-doctors")) == 5 for i in range(r.count()))
