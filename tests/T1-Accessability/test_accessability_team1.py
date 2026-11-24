import importlib.util
import os
import sys
from pathlib import Path

import pytest
# ==========================================================
# Django setup 
# ==========================================================
REPO_ROOT = Path(__file__).resolve().parent  # adjust parents[n] if this file lives in tests/
sys.path.insert(0, str(REPO_ROOT / "src" / "webapp"))  # adjust if your layout differs

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
def require_routes():
    """Fail the running test if any *_URL constant above does not resolve."""
    from django.urls import resolve

    urls = [v for k, v in globals().items() if k.endswith("_URL") and isinstance(v, str)]
    missing = []
    for url in urls:
        try:
            resolve(url)
        except Exception:  # Resolver404, or the urlconf module not existing yet
            missing.append(url)
    if missing:
        pytest.fail(f"Not implemented: no route for {missing}", pytrace=False)


@pytest.fixture
def client():
    """
    Django test client that fails with 'Not implemented' if the routes are missing.

    The check runs on the first request, i.e. inside the test body, so pytest
    reports FAILED instead of a fixture-setup ERROR.
    """
    from django.test import Client

    class GuardedClient(Client):
        def request(self, **request):
            require_routes()
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

def test_t1_01_valid_admin_account(client, login):
    """Login using a valid admin account: admin logs in and reaches the admin interface."""
    response = login("admin")

    assert response.status_code == 302
    assert response["Location"] == ADMIN_DASHBOARD_URL
    assert SESSION_KEY in client.session


def test_t1_02_valid_staff_account(client, login):
    """Login using a valid staff account: staff reaches the staff interface."""
    response = login("staff")

    assert response.status_code == 302
    assert response["Location"] == STAFF_SCHEDULE_URL
    assert SESSION_KEY in client.session


def test_t1_03_invalid_credentials(client):
    """Invalid credentials are rejected and an error is shown on the form."""
    response = client.post(
        LOGIN_URL,
        {"username": "invalid-user", "password": "invalid-password"},
    )

    assert response.status_code == 200
    assert SESSION_KEY not in client.session
    assert get_form(response).errors


def test_t1_04_logout(client, login):
    """Logout logs the user out and returns them to the login page."""
    login("staff")
    assert SESSION_KEY in client.session

    response = client.post(LOGOUT_URL)

    assert response.status_code == 302
    assert response["Location"].split("?")[0] == LOGIN_URL
    assert SESSION_KEY not in client.session


def test_t1_05_correct_username_and_password(client, login):
    """Correct username and password are accepted."""
    response = login("admin")

    assert response.status_code == 302
    assert SESSION_KEY in client.session


def test_t1_06_correct_username_incorrect_password(client, users):
    """Correct username with incorrect password is rejected."""
    response = client.post(
        LOGIN_URL,
        {"username": users["admin"][0], "password": "definitely-incorrect-password"},
    )

    assert response.status_code == 200
    assert SESSION_KEY not in client.session
    assert get_form(response).errors


def test_t1_07_incorrect_username_correct_password(client, users):
    """Incorrect username with correct password is rejected."""
    response = client.post(
        LOGIN_URL,
        {"username": "definitely-invalid-user", "password": users["admin"][1]},
    )

    assert response.status_code == 200
    assert SESSION_KEY not in client.session
    assert get_form(response).errors


@pytest.mark.skip(reason="Deferred: needs Playwright/Selenium to click the rendered Login button.")
def test_t1_08_login_button():
    """Submitting username and password via the Login button executes the login process."""


@pytest.mark.skip(reason="Deferred: needs Playwright/Selenium to press Enter in the rendered form.")
def test_t1_09_enter_key_after_credentials():
    """Pressing Enter after credentials triggers login."""


def test_t1_10_session_remains_active(client, login):
    """An authenticated session remains active while navigating protected pages."""
    login("staff")

    first = client.get(STAFF_SCHEDULE_URL)
    second = client.get(STAFF_SCHEDULE_URL)

    assert first.status_code == 200
    assert second.status_code == 200
    assert SESSION_KEY in client.session


def test_t1_11_logout_terminates_session(client, login):
    """Logout properly terminates the session."""
    login("staff")
    assert SESSION_KEY in client.session

    client.post(LOGOUT_URL)

    assert SESSION_KEY not in client.session


def test_t1_12_empty_username_and_password(client):
    """Empty username and password submission is rejected with required-field errors."""
    response = client.post(LOGIN_URL, {})

    assert response.status_code == 200
    assert SESSION_KEY not in client.session
    errors = get_form(response).errors
    assert "username" in errors
    assert "password" in errors


def test_t1_13_username_only(client, users):
    """A username-only submission is rejected with a password error."""
    response = client.post(LOGIN_URL, {"username": users["staff"][0]})

    assert response.status_code == 200
    assert SESSION_KEY not in client.session
    assert "password" in get_form(response).errors


def test_t1_14_password_only(client, users):
    """A password-only submission is rejected with a username error."""
    response = client.post(LOGIN_URL, {"password": users["staff"][1]})

    assert response.status_code == 200
    assert SESSION_KEY not in client.session
    assert "username" in get_form(response).errors


def test_t1_15_leading_trailing_spaces(client, users):
    """Leading/trailing spaces in username are trimmed and authenticate successfully."""
    # The RTM leaves whitespace handling open; this test assumes trimming is intended.
    username, password = users["staff"]

    response = client.post(
        LOGIN_URL,
        {"username": f"  {username}  ", "password": password},
    )

    assert response.status_code == 302
    assert SESSION_KEY in client.session


def test_t1_16_extremely_long_credentials(client):
    """Extremely long username/password input is handled safely."""
    response = client.post(
        LOGIN_URL,
        {"username": "u" * 10000, "password": "p" * 10000},
    )

    assert response.status_code in (200, 400, 413)
    assert SESSION_KEY not in client.session


def test_t1_17_special_characters(client):
    """Special characters are processed safely and cannot bypass authentication."""
    response = client.post(
        LOGIN_URL,
        {"username": "' OR '1'='1", "password": "' OR '1'='1"},
    )

    assert response.status_code in (200, 400)
    assert SESSION_KEY not in client.session


def test_t1_18_repeated_failed_logins(client):
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


def test_t1_19_staff_cannot_open_admin_dashboard(client, login):
    """Staff access to the admin dashboard URL is denied."""
    assert login("staff").status_code == 302

    response = client.get(ADMIN_DASHBOARD_URL)

    assert response.status_code == 403


def test_t1_20_staff_admin_only_functions(client, login):
    """Staff cannot perform administrative operations."""
    assert login("staff").status_code == 302

    response = client.post(ADMIN_ACTION_URL, {})

    assert response.status_code == 403


def test_t1_21_admin_permissions(client, login):
    """Admin permissions are recognised on the admin dashboard."""
    assert login("admin").status_code == 302

    response = client.get(ADMIN_DASHBOARD_URL)

    assert response.status_code == 200


def test_t1_22_logout_revisit_protected_page(client, login):
    """A logged-out user revisiting a protected page must authenticate again."""
    login("staff")
    client.post(LOGOUT_URL)

    response = client.get(STAFF_SCHEDULE_URL)

    assert response.status_code == 302
    assert response["Location"].split("?")[0] == LOGIN_URL


def test_t1_23_expired_session(client, login):
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