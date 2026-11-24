"""Login fixtures (admin / staff) and the pre-loaded dashboard data fixture."""
import pytest
from common import *


@pytest.fixture
def admin(page):
    login(page, ADMIN)
    return page


@pytest.fixture
def staff(page):
    login(page, STAFF)
    return page


@pytest.fixture
def loaded(admin, tmp_path):
    assert upload(admin, "ED", ed_file(tmp_path, ED_DASH))[0]
    assert upload(admin, "ICU", icu_file(tmp_path, ICU_DASH))[0]
    return admin
