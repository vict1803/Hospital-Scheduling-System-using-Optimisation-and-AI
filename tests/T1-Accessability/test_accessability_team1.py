import importlib.util
import os
import sys
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
# ==========================================================
# Django setup 
# ==========================================================
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

APP_SETTINGS = os.environ.get("DJANGO_SETTINGS_MODULE", "webapp.settings")


def _module_exists(name):
    """True if the dotted module can be found."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _configure_django():
    """Use the real app settings if present, else a minimal in-memory stand-in."""
    import django
    from django.conf import settings

    if _module_exists(APP_SETTINGS):
        os.environ["DJANGO_SETTINGS_MODULE"] = APP_SETTINGS
    elif not settings.configured:
        settings.configure(
            SECRET_KEY="test-only-key",
            ALLOWED_HOSTS=["testserver"],
            DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
            INSTALLED_APPS=[
                "django.contrib.auth",
                "django.contrib.contenttypes",
                "django.contrib.sessions",
            ],
            MIDDLEWARE=[
                "django.contrib.sessions.middleware.SessionMiddleware",
                "django.contrib.auth.middleware.AuthenticationMiddleware",
            ],
            ROOT_URLCONF="webapp.urls",
            DEFAULT_AUTO_FIELD="django.db.models.AutoField",
        )
    django.setup()


_configure_django()

# Every test touches the auth tables, so allow DB access for the whole module.
pytestmark = pytest.mark.django_db

# ==========================================================
# URL contract (decide here, once; record changes in the RTM)
# ==========================================================
LOGIN_URL = "/login/"
LOGOUT_URL = "/logout/"
ADMIN_DASHBOARD_URL = "/admin-dashboard/"
STAFF_SCHEDULE_URL = "/my-schedule/"
ADMIN_ACTION_URL = "/admin-dashboard/generate-roster/"

SESSION_KEY = "_auth_user_id"


# ==========================================================
# Fixtures and helpers
# ==========================================================
def require_routes(url):
    """Fail the running test if the requested URL does not resolve."""
    from django.urls import resolve

    try:
        resolve(url)
    except Exception:  # Resolver404, or the urlconf module not existing yet
        pytest.fail(f"Not implemented: no route for [{url}]", pytrace=False)


@pytest.fixture
def client():
    """
    Django test client that fails with 'Not implemented' if the requested route is missing.

    The check runs on the first request, i.e. inside the test body, so pytest
    reports FAILED instead of a fixture-setup ERROR.
    """
    from django.test import Client

    class GuardedClient(Client):
        def request(self, **request):
            require_routes(request["PATH_INFO"])
            return super().request(**request)

    return GuardedClient()


@pytest.fixture
def users(db, django_user_model):
    """Create one admin and one staff account in the test database."""
    admin = django_user_model.objects.create_user(
        username="admin1", password="Adm1n-test-pass", is_staff=True
    )
    staff = django_user_model.objects.create_user(
        username="nurse1", password="Staff-test-pass"
    )
    return {"admin": (admin.username, "Adm1n-test-pass"),
            "staff": (staff.username, "Staff-test-pass")}


@pytest.fixture
def login(client, users):
    """Return a function that logs in as 'admin' or 'staff'."""
    def _login(role):
        username, password = users[role]
        return client.post(LOGIN_URL, {"username": username, "password": password})
    return _login


def get_form(response):
    """Return the login form from a rendered response, failing clearly if absent."""
    assert response.context is not None, "Login response must render a template."
    form = response.context.get("form")
    assert form is not None, "Login template must expose the form as 'form'."
    return form

# ==========================================================
# R01 - Secure Role-Based Login
# ==========================================================

def test_t1_r01_01_valid_admin_account(client, login):
    """Login using a valid admin account: admin logs in and reaches the admin interface."""
    response = login("admin")

    assert response.status_code == 302
    assert response["Location"] == ADMIN_DASHBOARD_URL
    assert SESSION_KEY in client.session

def test_t1_r01_02_valid_staff_account(client, login):
    """Login using a valid staff account: staff reaches the staff interface."""
    response = login("staff")

    assert response.status_code == 302
    assert response["Location"] == STAFF_SCHEDULE_URL
    assert SESSION_KEY in client.session

def test_t1_r01_03_invalid_credentials(client):
    """Invalid credentials are rejected and an error is shown on the form."""
    response = client.post(
        LOGIN_URL,
        {"username": "invalid-user", "password": "invalid-password"},
    )

    assert response.status_code == 200
    assert SESSION_KEY not in client.session
    assert get_form(response).errors

def test_t1_r01_04_logout(client, login):
    """Logout logs the user out and returns them to the login page."""
    login("staff")
    assert SESSION_KEY in client.session

    response = client.post(LOGOUT_URL)

    assert response.status_code == 302
    assert response["Location"].split("?")[0] == LOGIN_URL
    assert SESSION_KEY not in client.session

def test_t1_r01_05_correct_username_and_password(client, login):
    """Correct username and password are accepted."""
    response = login("admin")

    assert response.status_code == 302
    assert SESSION_KEY in client.session

def test_t1_r01_06_correct_username_incorrect_password(client, users):
    """Correct username with incorrect password is rejected."""
    response = client.post(
        LOGIN_URL,
        {"username": users["admin"][0], "password": "definitely-incorrect-password"},
    )

    assert response.status_code == 200
    assert SESSION_KEY not in client.session
    assert get_form(response).errors

def test_t1_r01_07_incorrect_username_correct_password(client, users):
    """Incorrect username with correct password is rejected."""
    response = client.post(
        LOGIN_URL,
        {"username": "definitely-invalid-user", "password": users["admin"][1]},
    )

    assert response.status_code == 200
    assert SESSION_KEY not in client.session
    assert get_form(response).errors

@pytest.mark.skip(reason="Deferred: needs Playwright/Selenium to click the rendered Login button.")
def test_t1_r01_08_login_button():
    """Submitting username and password via the Login button executes the login process."""

@pytest.mark.skip(reason="Deferred: needs Playwright/Selenium to press Enter in the rendered form.")
def test_t1_r01_09_enter_key_after_credentials():
    """Pressing Enter after credentials triggers login."""

def test_t1_r01_10_session_remains_active(client, login):
    """An authenticated session remains active while navigating protected pages."""
    login("staff")

    first = client.get(STAFF_SCHEDULE_URL)
    second = client.get(STAFF_SCHEDULE_URL)

    assert first.status_code == 200
    assert second.status_code == 200
    assert SESSION_KEY in client.session

def test_t1_r01_11_logout_terminates_session(client, login):
    """Logout properly terminates the session."""
    login("staff")
    assert SESSION_KEY in client.session

    client.post(LOGOUT_URL)

    assert SESSION_KEY not in client.session

def test_t1_r01_12_empty_username_and_password(client):
    """Empty username and password submission is rejected with required-field errors."""
    response = client.post(LOGIN_URL, {})

    assert response.status_code == 200
    assert SESSION_KEY not in client.session
    errors = get_form(response).errors
    assert "username" in errors
    assert "password" in errors

def test_t1_r01_13_username_only(client, users):
    """A username-only submission is rejected with a password error."""
    response = client.post(LOGIN_URL, {"username": users["staff"][0]})

    assert response.status_code == 200
    assert SESSION_KEY not in client.session
    assert "password" in get_form(response).errors

def test_t1_r01_14_password_only(client, users):
    """A password-only submission is rejected with a username error."""
    response = client.post(LOGIN_URL, {"password": users["staff"][1]})

    assert response.status_code == 200
    assert SESSION_KEY not in client.session
    assert "username" in get_form(response).errors

def test_t1_r01_15_leading_trailing_spaces(client, users):
    """Leading/trailing spaces in username are trimmed and authenticate successfully."""
    # The RTM leaves whitespace handling open; this test assumes trimming is intended.
    username, password = users["staff"]

    response = client.post(
        LOGIN_URL,
        {"username": f"  {username}  ", "password": password},
    )

    assert response.status_code == 302
    assert SESSION_KEY in client.session

def test_t1_r01_16_extremely_long_credentials(client):
    """Extremely long username/password input is handled safely."""
    response = client.post(
        LOGIN_URL,
        {"username": "u" * 10000, "password": "p" * 10000},
    )

    assert response.status_code in (200, 400, 413)
    assert SESSION_KEY not in client.session

def test_t1_r01_17_special_characters(client):
    """Special characters are processed safely and cannot bypass authentication."""
    response = client.post(
        LOGIN_URL,
        {"username": "' OR '1'='1", "password": "' OR '1'='1"},
    )

    assert response.status_code in (200, 400)
    assert SESSION_KEY not in client.session

def test_t1_r01_18_repeated_failed_logins(client):
    """
    Repeated failed credentials do not grant access.

    Lockout is not specified in R01, so this test does not require a lockout
    threshold; it only verifies that authentication remains denied.
    """
    for _ in range(5):
        response = client.post(
            LOGIN_URL,
            {"username": "invalid-user", "password": "invalid-password"},
        )
        assert response.status_code in (200, 429)
        assert SESSION_KEY not in client.session

def test_t1_r01_19_staff_cannot_open_admin_dashboard(client, login):
    """Staff access to the admin dashboard URL is denied."""
    assert login("staff").status_code == 302

    response = client.get(ADMIN_DASHBOARD_URL)

    assert response.status_code == 403

def test_t1_r01_20_staff_admin_only_functions(client, login):
    """Staff cannot perform administrative operations."""
    assert login("staff").status_code == 302

    response = client.post(ADMIN_ACTION_URL, {})

    assert response.status_code == 403

def test_t1_r01_21_admin_permissions(client, login):
    """Admin permissions are recognised on the admin dashboard."""
    assert login("admin").status_code == 302

    response = client.get(ADMIN_DASHBOARD_URL)

    assert response.status_code == 200

def test_t1_r01_22_logout_revisit_protected_page(client, login):
    """A logged-out user revisiting a protected page must authenticate again."""
    login("staff")
    client.post(LOGOUT_URL)

    response = client.get(STAFF_SCHEDULE_URL)

    assert response.status_code == 302
    assert response["Location"].split("?")[0] == LOGIN_URL

def test_t1_r01_23_expired_session(client, login):
    """An expired session requires reauthentication."""
    login("staff")

    # client.session returns a NEW object on every access, so keep one
    # reference and save it, otherwise the expiry is never persisted.
    session = client.session
    session.set_expiry(-1)  # one second in the past (DB session backend)
    session.save()

    response = client.get(STAFF_SCHEDULE_URL)

    assert response.status_code == 302
    assert response["Location"].split("?")[0] == LOGIN_URL


# ==========================================================
# R02 - Admin Dashboard
# ==========================================================

SCHEDULE_ROW_FIELDS = {"staff_id", "ward_id", "shift_date", "shift_name"}

@pytest.fixture
def dashboard_test_data_factory(db):
    """Seed dashboard records and return expected rows plus fixture identifiers.

    The result includes schedule_rows, ward_ids, empty_ward_id, week_start,
    month_start, and period_without_roster.
    """
    def _create_dashboard_test_data(row_count=6):
        from webapp.testing import create_dashboard_test_data

        return create_dashboard_test_data(row_count=row_count)

    return _create_dashboard_test_data

def _login_admin(login):
    login_response = login("admin")
    assert login_response.status_code == 302

def _admin_dashboard(client, login):
    _login_admin(login)
    return client.get(ADMIN_DASHBOARD_URL)

def _admin_dashboard_with_data(client, login, dashboard_test_data_factory, row_count=6):
    _login_admin(login)
    test_data = dashboard_test_data_factory(row_count=row_count)
    response = client.get(ADMIN_DASHBOARD_URL)
    return test_data, response

def _schedule_rows(response):
    assert response.context is not None, "Dashboard response must expose its template context."
    assert "schedule_rows" in response.context
    rows = response.context["schedule_rows"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, Mapping)
        assert SCHEDULE_ROW_FIELDS <= row.keys()
    return rows

def _normalized_rows(rows):
    return sorted(
        (
            str(row["staff_id"]),
            str(row["ward_id"]),
            _as_date(row["shift_date"]).isoformat(),
            str(row["shift_name"]),
        )
        for row in rows
    )

def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])

def _rows_for_period(rows, period_start, period_type):
    period_start = _as_date(period_start)
    if period_type == "week":
        return [
            row for row in rows
            if period_start <= _as_date(row["shift_date"]) < period_start + timedelta(days=7)
        ]
    return [
        row for row in rows
        if (_as_date(row["shift_date"]).year, _as_date(row["shift_date"]).month)
        == (period_start.year, period_start.month)
    ]

def test_t1_r02_24_admin_dashboard_after_login(client, login):
    """Admin opens the dashboard after logging in."""
    response = _admin_dashboard(client, login)

    assert response.status_code == 200

def test_t1_r02_25_overall_staff_schedule(client, login, dashboard_test_data_factory):
    """Admin views the overall staff schedule across relevant wards."""
    test_data, response = _admin_dashboard_with_data(
        client, login, dashboard_test_data_factory
    )

    assert response.status_code == 200
    assert _normalized_rows(_schedule_rows(response)) == _normalized_rows(
        test_data["schedule_rows"]
    )

def test_t1_r02_26_schedule_for_selected_period(client, login, dashboard_test_data_factory):
    """Admin views schedules for a selected period."""
    test_data, _ = _admin_dashboard_with_data(
        client, login, dashboard_test_data_factory
    )
    period_start = _as_date(test_data["week_start"])

    response = client.get(
        ADMIN_DASHBOARD_URL,
        {"period_start": period_start.isoformat(), "period_type": "week"},
    )

    assert response.status_code == 200
    rows = _schedule_rows(response)
    assert _normalized_rows(rows) == _normalized_rows(
        _rows_for_period(test_data["schedule_rows"], period_start, "week")
    )

def test_t1_r02_27_schedule_for_another_ward(client, login, dashboard_test_data_factory):
    """Admin navigates to another ward."""
    test_data, _ = _admin_dashboard_with_data(
        client, login, dashboard_test_data_factory
    )
    selected_ward = test_data["ward_ids"][1]

    response = client.get(ADMIN_DASHBOARD_URL, {"ward_id": selected_ward})

    assert response.status_code == 200
    assert _normalized_rows(_schedule_rows(response)) == _normalized_rows(
        [row for row in test_data["schedule_rows"] if row["ward_id"] == selected_ward]
    )

def test_t1_r02_28_open_dashboard_from_navigation(client, login):
    """Open the dashboard from the navigation menu."""
    response = _admin_dashboard(client, login)

    assert response.status_code == 200
    assert f'href="{ADMIN_DASHBOARD_URL}"'.encode() in response.content

def test_t1_r02_29_select_ward(client, login, dashboard_test_data_factory):
    """Selecting a ward displays that ward on the dashboard."""
    test_data, _ = _admin_dashboard_with_data(
        client, login, dashboard_test_data_factory
    )
    selected_ward = test_data["ward_ids"][0]

    response = client.get(ADMIN_DASHBOARD_URL, {"ward_id": selected_ward})

    assert response.status_code == 200
    assert _normalized_rows(_schedule_rows(response)) == _normalized_rows(
        [row for row in test_data["schedule_rows"] if row["ward_id"] == selected_ward]
    )

def test_t1_r02_30_select_scheduling_period(client, login, dashboard_test_data_factory):
    """Selecting a different scheduling period updates the schedule."""
    test_data, _ = _admin_dashboard_with_data(
        client, login, dashboard_test_data_factory
    )
    period_start = _as_date(test_data["month_start"])

    response = client.get(
        ADMIN_DASHBOARD_URL,
        {"period_start": period_start.isoformat(), "period_type": "month"},
    )

    assert response.status_code == 200
    assert _normalized_rows(_schedule_rows(response)) == _normalized_rows(
        _rows_for_period(test_data["schedule_rows"], period_start, "month")
    )

def test_t1_r02_31_navigate_between_wards(client, login, dashboard_test_data_factory):
    """Navigating between wards updates the selected ward and schedule."""
    test_data, _ = _admin_dashboard_with_data(
        client, login, dashboard_test_data_factory
    )
    ward_ids = test_data["ward_ids"]

    first_response = client.get(ADMIN_DASHBOARD_URL, {"ward_id": ward_ids[0]})
    second_response = client.get(ADMIN_DASHBOARD_URL, {"ward_id": ward_ids[1]})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert _normalized_rows(_schedule_rows(first_response)) == _normalized_rows(
        [row for row in test_data["schedule_rows"] if row["ward_id"] == ward_ids[0]]
    )
    assert _normalized_rows(_schedule_rows(second_response)) == _normalized_rows(
        [row for row in test_data["schedule_rows"] if row["ward_id"] == ward_ids[1]]
    )

def test_t1_r02_32_navigate_between_periods(client, login, dashboard_test_data_factory):
    """Navigating between weeks or months updates the schedule."""
    test_data, _ = _admin_dashboard_with_data(
        client, login, dashboard_test_data_factory
    )
    week_start = _as_date(test_data["week_start"])
    month_start = _as_date(test_data["month_start"])

    week_response = client.get(
        ADMIN_DASHBOARD_URL,
        {"period_start": week_start.isoformat(), "period_type": "week"},
    )
    month_response = client.get(
        ADMIN_DASHBOARD_URL,
        {"period_start": month_start.isoformat(), "period_type": "month"},
    )

    assert week_response.status_code == 200
    assert month_response.status_code == 200
    assert _normalized_rows(_schedule_rows(week_response)) == _normalized_rows(
        _rows_for_period(test_data["schedule_rows"], week_start, "week")
    )
    assert _normalized_rows(_schedule_rows(month_response)) == _normalized_rows(
        _rows_for_period(test_data["schedule_rows"], month_start, "month")
    )

def test_t1_r02_33_refresh_dashboard(client, login, dashboard_test_data_factory):
    """Refreshing the dashboard preserves data integrity."""
    test_data, first_response = _admin_dashboard_with_data(
        client, login, dashboard_test_data_factory
    )
    refreshed_response = client.get(ADMIN_DASHBOARD_URL)

    assert refreshed_response.status_code == 200
    expected_rows = _normalized_rows(test_data["schedule_rows"])
    assert _normalized_rows(_schedule_rows(first_response)) == expected_rows
    assert _normalized_rows(_schedule_rows(refreshed_response)) == expected_rows

def test_t1_r02_34_ward_with_no_assigned_staff(client, login, dashboard_test_data_factory):
    """Selecting a ward with no assigned staff displays an empty state."""
    test_data, _ = _admin_dashboard_with_data(
        client, login, dashboard_test_data_factory
    )

    response = client.get(
        ADMIN_DASHBOARD_URL,
        {"ward_id": test_data["empty_ward_id"]},
    )

    assert response.status_code == 200
    assert _schedule_rows(response) == []

def test_t1_r02_35_period_without_roster(client, login, dashboard_test_data_factory):
    """Selecting a period without a roster displays an appropriate empty state."""
    test_data, _ = _admin_dashboard_with_data(
        client, login, dashboard_test_data_factory
    )

    response = client.get(
        ADMIN_DASHBOARD_URL,
        {
            "period_start": test_data["period_without_roster"],
            "period_type": "week",
        },
    )

    assert response.status_code == 200
    assert _schedule_rows(response) == []

def test_t1_r02_36_invalid_or_unavailable_period(client, login):
    """Selecting an invalid or unavailable period does not show incorrect data."""
    _admin_dashboard(client, login)

    response = client.get(
        ADMIN_DASHBOARD_URL,
        {"period_start": "not-a-date", "period_type": "week"},
    )

    assert response.status_code in (200, 400)
    if response.status_code == 200:
        assert _schedule_rows(response) == []

def test_t1_r02_37_large_number_of_staff_entries(client, login, dashboard_test_data_factory):
    """A 100-row schedule is fully returned without an HTTP error."""
    test_data, response = _admin_dashboard_with_data(
        client, login, dashboard_test_data_factory, row_count=100
    )

    # Django's test client checks the rendered data, not browser layout at a viewport.
    assert response.status_code == 200
    expected_rows = test_data["schedule_rows"]
    actual_rows = _schedule_rows(response)
    assert len(expected_rows) >= 100
    assert _normalized_rows(actual_rows) == _normalized_rows(expected_rows)

def test_t1_r02_38_rapidly_switch_between_wards(
    client, login, dashboard_test_data_factory
):
    """Successive HTTP requests return matching schedules; browser races are not tested."""
    test_data, _ = _admin_dashboard_with_data(
        client, login, dashboard_test_data_factory
    )
    ward_ids = test_data["ward_ids"]

    first_response = client.get(ADMIN_DASHBOARD_URL, {"ward_id": ward_ids[0]})
    second_response = client.get(ADMIN_DASHBOARD_URL, {"ward_id": ward_ids[1]})
    final_response = client.get(ADMIN_DASHBOARD_URL, {"ward_id": ward_ids[0]})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert final_response.status_code == 200
    for response, selected_ward in (
        (first_response, ward_ids[0]),
        (second_response, ward_ids[1]),
        (final_response, ward_ids[0]),
    ):
        expected_rows = [
            row for row in test_data["schedule_rows"]
            if row["ward_id"] == selected_ward
        ]
        assert _normalized_rows(_schedule_rows(response)) == _normalized_rows(
            expected_rows
        )

def test_t1_r02_39_refresh_dashboard_with_filter(
    client, login, dashboard_test_data_factory
):
    """Refreshing while a filter is active does not show unrelated data."""
    test_data, _ = _admin_dashboard_with_data(
        client, login, dashboard_test_data_factory
    )
    selected_ward = test_data["ward_ids"][0]
    period_start = _as_date(test_data["week_start"])
    filters = {
        "ward_id": selected_ward,
        "period_start": period_start.isoformat(),
        "period_type": "week",
    }

    first_response = client.get(ADMIN_DASHBOARD_URL, filters)
    refreshed_response = client.get(ADMIN_DASHBOARD_URL, filters)

    assert first_response.status_code == 200
    assert refreshed_response.status_code == 200
    first_rows = _schedule_rows(first_response)
    refreshed_rows = _schedule_rows(refreshed_response)
    expected_rows = [
        row for row in test_data["schedule_rows"]
        if str(row["ward_id"]) == str(selected_ward)
        and row in _rows_for_period(test_data["schedule_rows"], period_start, "week")
    ]
    assert _normalized_rows(first_rows) == _normalized_rows(expected_rows)
    assert _normalized_rows(refreshed_rows) == _normalized_rows(expected_rows)

def test_t1_r02_40_dashboard_staff_match_roster(
    client, login, dashboard_test_data_factory
):
    """Staff identifiers shown on the dashboard match roster records."""
    test_data, response = _admin_dashboard_with_data(
        client, login, dashboard_test_data_factory
    )
    expected_staff_ids = sorted(str(row["staff_id"]) for row in test_data["schedule_rows"])

    assert sorted(str(row["staff_id"]) for row in _schedule_rows(response)) == expected_staff_ids

def test_t1_r02_41_dashboard_dates_and_shifts_match_roster(
    client, login, dashboard_test_data_factory
):
    """Dashboard dates and shifts match the roster records."""
    test_data, response = _admin_dashboard_with_data(
        client, login, dashboard_test_data_factory
    )
    expected_date_shifts = sorted(
        (
            str(row["staff_id"]),
            str(row["ward_id"]),
            _as_date(row["shift_date"]).isoformat(),
            str(row["shift_name"]),
        )
        for row in test_data["schedule_rows"]
    )
    actual_date_shifts = sorted(
        (
            str(row["staff_id"]),
            str(row["ward_id"]),
            _as_date(row["shift_date"]).isoformat(),
            str(row["shift_name"]),
        )
        for row in _schedule_rows(response)
    )

    assert actual_date_shifts == expected_date_shifts

def test_t1_r02_42_selected_ward_excludes_unrelated_staff(
    client, login, dashboard_test_data_factory
):
    """Ward-specific filtering excludes staff from unrelated wards."""
    test_data, _ = _admin_dashboard_with_data(
        client, login, dashboard_test_data_factory
    )
    selected_ward = test_data["ward_ids"][0]

    response = client.get(ADMIN_DASHBOARD_URL, {"ward_id": selected_ward})

    assert response.status_code == 200
    expected_rows = [
        row for row in test_data["schedule_rows"]
        if row["ward_id"] == selected_ward
    ]
    assert _normalized_rows(_schedule_rows(response)) == _normalized_rows(expected_rows)

def test_t1_r02_43_dashboard_schedule_counts_match_roster(
    client, login, dashboard_test_data_factory
):
    """Dashboard shift counts per ward match the roster records."""
    test_data, response = _admin_dashboard_with_data(
        client, login, dashboard_test_data_factory
    )

    def counts_by_ward(rows):
        counts = {}
        for row in rows:
            ward_id = str(row["ward_id"])
            counts[ward_id] = counts.get(ward_id, 0) + 1
        return counts

    assert counts_by_ward(_schedule_rows(response)) == counts_by_ward(
        test_data["schedule_rows"]
    )


# ==========================================================
# R03 - Individual Staff Schedule
# ==========================================================

STAFF_SCHEDULE_ROW_FIELDS = {
    "staff_id",
    "shift_date",
    "shift_name",
    "start_time",
    "end_time",
}


def _staff_schedule(client, login, params=None, method="get"):
    login_response = login("staff")
    assert login_response.status_code == 302
    request = getattr(client, method)
    return request(STAFF_SCHEDULE_URL, params or {})


def _staff_schedule_rows(response):
    assert response.context is not None, "Staff schedule must expose its template context."
    assert "schedule_rows" in response.context
    rows = response.context["schedule_rows"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, Mapping)
        assert STAFF_SCHEDULE_ROW_FIELDS <= row.keys()
    return rows


def _staff_rows_for_week(rows, week_start):
    week_start = _as_date(week_start)
    return [
        row for row in rows
        if week_start <= _as_date(row["shift_date"]) < week_start + timedelta(days=7)
    ]


def _current_week_start():
    today = date.today()
    return today - timedelta(days=today.weekday())


def _assert_only_logged_in_staff(rows, users, django_user_model):
    staff_user = django_user_model.objects.get(username=users["staff"][0])
    assert all(str(row["staff_id"]) == str(staff_user.pk) for row in rows)


def test_t1_r03_44_staff_opens_own_schedule(client, login, users, django_user_model):
    """A staff member can open a schedule containing only their own shifts."""
    response = _staff_schedule(client, login)

    assert response.status_code == 200
    rows = _staff_schedule_rows(response)
    assert rows
    _assert_only_logged_in_staff(rows, users, django_user_model)


def test_t1_r03_45_staff_views_current_week(client, login):
    """The schedule for the current week contains only current-week shifts."""
    week_start = _current_week_start()
    response = _staff_schedule(
        client,
        login,
        {"period_start": week_start.isoformat(), "period_type": "week"},
    )

    assert response.status_code == 200
    rows = _staff_schedule_rows(response)
    assert rows
    assert rows == _staff_rows_for_week(rows, week_start)


def test_t1_r03_46_staff_selects_another_period(client, login):
    """Selecting another scheduling period displays shifts from that period."""
    week_start = _current_week_start() + timedelta(days=7)
    response = _staff_schedule(
        client,
        login,
        {"period_start": week_start.isoformat(), "period_type": "week"},
    )

    assert response.status_code == 200
    rows = _staff_schedule_rows(response)
    assert rows
    assert rows == _staff_rows_for_week(rows, week_start)


def test_t1_r03_47_staff_with_no_assigned_shifts_sees_empty_state(client, login):
    """A staff member without assigned shifts sees an empty schedule."""
    response = _staff_schedule(client, login)

    assert response.status_code == 200
    assert _staff_schedule_rows(response) == []


def test_t1_r03_48_open_schedule_from_navigation(client, login):
    """The staff navigation menu links to the individual schedule."""
    response = _staff_schedule(client, login)

    assert response.status_code == 200
    assert f'href="{STAFF_SCHEDULE_URL}"'.encode() in response.content


def test_t1_r03_49_staff_selects_a_different_week(client, login):
    """Selecting a different week updates the displayed schedule."""
    week_start = _current_week_start() - timedelta(days=7)
    response = _staff_schedule(
        client,
        login,
        {"period_start": week_start.isoformat(), "period_type": "week"},
    )

    assert response.status_code == 200
    rows = _staff_schedule_rows(response)
    assert rows
    assert rows == _staff_rows_for_week(rows, week_start)


def test_t1_r03_50_shift_dates_times_and_types_are_displayed(client, login):
    """Each displayed shift includes its date, start/end times, and shift type."""
    response = _staff_schedule(client, login)

    assert response.status_code == 200
    rows = _staff_schedule_rows(response)
    assert rows
    for row in rows:
        _as_date(row["shift_date"])
        assert row["start_time"] is not None
        assert row["end_time"] is not None
        assert row["shift_name"]


def test_t1_r03_51_refresh_preserves_schedule(client, login):
    """Refreshing the staff schedule returns the same shift data."""
    first_response = _staff_schedule(client, login)
    refreshed_response = client.get(STAFF_SCHEDULE_URL)

    assert first_response.status_code == 200
    assert refreshed_response.status_code == 200
    assert _staff_schedule_rows(refreshed_response) == _staff_schedule_rows(
        first_response
    )


def test_t1_r03_52_navigate_back_and_forward_between_periods(client, login):
    """Back/forward period requests return shifts for their requested weeks."""
    current_week = _current_week_start()
    previous_week = current_week - timedelta(days=7)
    next_week = current_week + timedelta(days=7)
    previous_response = _staff_schedule(
        client,
        login,
        {"period_start": previous_week.isoformat(), "period_type": "week"},
    )
    next_response = client.get(
        STAFF_SCHEDULE_URL,
        {"period_start": next_week.isoformat(), "period_type": "week"},
    )

    assert previous_response.status_code == 200
    assert next_response.status_code == 200
    previous_rows = _staff_schedule_rows(previous_response)
    next_rows = _staff_schedule_rows(next_response)
    assert previous_rows
    assert next_rows
    assert previous_rows == _staff_rows_for_week(previous_rows, previous_week)
    assert next_rows == _staff_rows_for_week(next_rows, next_week)


def test_t1_r03_53_selected_week_without_shifts_shows_empty_state(client, login):
    """A week with no shifts is represented as an empty schedule."""
    empty_week = _current_week_start() + timedelta(days=7 * 52)
    response = _staff_schedule(
        client,
        login,
        {"period_start": empty_week.isoformat(), "period_type": "week"},
    )

    assert response.status_code == 200
    assert _staff_schedule_rows(response) == []


def test_t1_r03_54_period_outside_roster_range_is_handled(client, login):
    """A period well beyond the roster range does not return unrelated shifts."""
    outside_period = date.today() + timedelta(days=365 * 10)
    week_start = outside_period - timedelta(days=outside_period.weekday())
    response = _staff_schedule(
        client,
        login,
        {"period_start": week_start.isoformat(), "period_type": "week"},
    )

    assert response.status_code == 200
    assert _staff_schedule_rows(response) == []


def test_t1_r03_55_url_cannot_expose_another_staff_schedule(
    client, login, users, django_user_model
):
    """Changing the staff_id URL parameter cannot expose another staff member's shifts."""
    other_staff = django_user_model.objects.create_user(
        username="nurse2", password="Other-staff-pass"
    )
    response = _staff_schedule(
        client, login, {"staff_id": other_staff.pk}
    )

    assert response.status_code in (200, 403, 404)
    if response.status_code == 200:
        _assert_only_logged_in_staff(
            _staff_schedule_rows(response), users, django_user_model
        )


def test_t1_r03_56_manipulated_request_cannot_expose_another_staff_schedule(
    client, login, users, django_user_model
):
    """A forged POST parameter cannot expose another staff member's shifts."""
    other_staff = django_user_model.objects.create_user(
        username="nurse2", password="Other-staff-pass"
    )
    response = _staff_schedule(
        client, login, {"staff_id": other_staff.pk}, method="post"
    )

    assert response.status_code in (200, 403, 404)
    if response.status_code == 200:
        _assert_only_logged_in_staff(
            _staff_schedule_rows(response), users, django_user_model
        )


def test_t1_r03_57_expired_session_requires_reauthentication(client, login):
    """An expired session cannot continue displaying the staff schedule."""
    assert login("staff").status_code == 302
    session = client.session
    session.set_expiry(-1)
    session.save()

    response = client.get(STAFF_SCHEDULE_URL)

    assert response.status_code == 302
    assert response["Location"].split("?")[0] == LOGIN_URL


def test_t1_r03_58_repeated_period_changes_do_not_show_stale_shifts(client, login):
    """Repeatedly changing periods returns rows belonging to each requested week."""
    current_week = _current_week_start()
    periods = [
        current_week,
        current_week + timedelta(days=7),
        current_week - timedelta(days=7),
    ]

    for week_start in periods:
        response = client.get(
            STAFF_SCHEDULE_URL,
            {"period_start": week_start.isoformat(), "period_type": "week"},
        )

        assert response.status_code == 200
        rows = _staff_schedule_rows(response)
        assert rows
        assert rows == _staff_rows_for_week(rows, week_start)


def test_t1_r03_59_individual_schedule_matches_master_roster(
    client, login, users, django_user_model, dashboard_test_data_factory
):
    """The staff schedule contains exactly their shifts from the master roster."""
    test_data = dashboard_test_data_factory()
    staff_user = django_user_model.objects.get(username=users["staff"][0])
    expected_rows = [
        row for row in test_data["schedule_rows"]
        if str(row["staff_id"]) == str(staff_user.pk)
    ]

    response = _staff_schedule(client, login)

    assert response.status_code == 200
    assert _normalized_rows(_staff_schedule_rows(response)) == _normalized_rows(
        expected_rows
    )


def test_t1_r03_60_only_logged_in_staff_id_is_displayed(
    client, login, users, django_user_model
):
    """Every schedule row belongs to the authenticated staff account."""
    response = _staff_schedule(client, login)

    assert response.status_code == 200
    rows = _staff_schedule_rows(response)
    assert rows
    _assert_only_logged_in_staff(rows, users, django_user_model)


def test_t1_r03_61_displayed_shift_dates_and_times_are_valid(client, login):
    """Shift dates and times are present and parse as valid values."""
    from datetime import time

    response = _staff_schedule(client, login)

    assert response.status_code == 200
    rows = _staff_schedule_rows(response)
    assert rows
    for row in rows:
        _as_date(row["shift_date"])
        time.fromisoformat(str(row["start_time"]))
        time.fromisoformat(str(row["end_time"]))


def test_t1_r03_62_schedule_reflects_administrator_roster_changes(
    client, login, users, django_user_model, dashboard_test_data_factory
):
    """The staff schedule reflects the current master roster after an admin update."""
    test_data = dashboard_test_data_factory()
    staff_user = django_user_model.objects.get(username=users["staff"][0])
    expected_rows = [
        row for row in test_data["schedule_rows"]
        if str(row["staff_id"]) == str(staff_user.pk)
    ]
    _login_admin(login)
    admin_response = client.post(ADMIN_ACTION_URL, {"action": "update"})
    assert admin_response.status_code in (200, 302)

    staff_login = login("staff")
    assert staff_login.status_code == 302
    response = client.get(STAFF_SCHEDULE_URL)

    assert response.status_code == 200
    assert _normalized_rows(_staff_schedule_rows(response)) == _normalized_rows(
        expected_rows
    )