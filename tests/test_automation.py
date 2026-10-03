import json

import automation
import config
import pytest
import template_loader

from automation import LoginError, PlaywrightTimeoutError, SimpegAutomator
from exceptions import JournalEntryError
from ui import RunGuard, request_automation_start


class FakeLocator:
    def __init__(self, text="", enabled=True):
        self._visible = True
        self._enabled = enabled
        self.clicked = False
        self.filled = None
        self.selected = None
        self.text = text

    def count(self):
        return 1

    @property
    def first(self):
        return self

    def is_visible(self):
        return self._visible

    def is_enabled(self):
        return self._enabled

    def wait_for(self, state=None, timeout=None):
        return True

    def fill(self, value):
        self.filled = value

    def select_option(self, value=None, label=None, timeout=None):
        self.selected = label if label is not None else value
        self.filled = self.selected
        self.text = self.selected or self.text

    def element_handles(self):
        return []

    def input_value(self):
        return self.filled or ""

    def locator(self, selector):
        return self

    def get_by_label(self, label_text):
        return self

    def inner_text(self):
        return self.text

    def filter(self, has_text=None):
        return self

    def get_by_role(self, role_name):
        return self

    def get_by_text(self, text, exact=False):
        return self

    def click(self):
        self.clicked = True

    def locator(self, selector):
        return self

    def nth(self, index):
        return self


class FakePopupContext:
    def __init__(self, popup_page):
        self.value = popup_page

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakePage:
    def __init__(self):
        self.clicked = False
        self.goto_url = None
        self.goto_wait_until = None
        self.goto_timeout = None
        self.wait_for_url_called = False
        self.wait_for_url_pattern = None
        self.url = ""
        self.page_defaults_set = False
        self.request_count = 0
        self.portal_visible = True
        self.timeout_on_attempts = set()
        self.force_timeout = False
        self.selectors = {}

    def locator(self, selector):
        return FakeLocator()

    def get_by_role(self, role_name, **kwargs):
        return FakeLocator()

    def get_by_text(self, text, exact=False):
        return FakeLocator(text=text)

    def click(self, selector):
        self.clicked = True

    def expect_popup(self):
        return FakePopupContext(self)

    def wait_for_load_state(self, state=None):
        return True

    def wait_for_url(self, url, timeout=None):
        self.wait_for_url_called = True
        self.wait_for_url_pattern = url
        return True

    def goto(self, url, wait_until=None, timeout=None):
        self.goto_url = url
        self.goto_wait_until = wait_until
        self.goto_timeout = timeout
        self.request_count += 1
        self.url = url
        if self.force_timeout or self.request_count in self.timeout_on_attempts:
            raise PlaywrightTimeoutError("timeout")
        return True

    def set_default_timeout(self, timeout):
        self.page_defaults_set = True

    def set_default_navigation_timeout(self, timeout):
        self.page_defaults_set = True


def test_dry_run_does_not_click_submit(monkeypatch):
    automator = SimpegAutomator("user", "pass", show_browser=False, dry_run=True)
    automator.page = FakePage()
    automator._set_state = lambda state: None
    automator._update_status = lambda message: None

    automator._submit_and_verify_journal()
    assert automator.page.clicked is False


def test_dry_run_enabled_by_default():
    assert config.DRY_RUN is True


def test_two_stage_login_waits_for_nip_and_password(monkeypatch):
    automator = SimpegAutomator("user", "pass", show_browser=False, dry_run=True)
    fake_page = FakePage()
    automator.page = fake_page
    automator._set_state = lambda state: None
    automator._update_status = lambda message: None

    wait_calls = []
    original_wait_for_selector = automator._wait_for_selector

    def fake_wait_for_selector(selector_key, timeout=None):
        wait_calls.append(selector_key)
        return FakeLocator()

    automator._click_selector = lambda selector_key: None
    automator._make_locator = lambda selector: FakeLocator()
    automator._wait_for_selector = fake_wait_for_selector

    automator._open_login_page()
    assert automator.page.wait_for_url_called
    assert automator.page.wait_for_url_pattern == "**/devp/siap/signin.php"
    assert "nip_input" in wait_calls

    automator._fill_login_step1()
    assert "password_input" in wait_calls
    assert automator.dry_run is True


def test_portal_navigation_uses_commit_and_portal_entry_check(monkeypatch):
    automator = SimpegAutomator("user", "pass", show_browser=False, dry_run=True)
    fake_page = FakePage()
    automator.page = fake_page
    automator._set_state = lambda state: None
    automator._update_status = lambda message: None
    automator._click_selector = lambda selector_key: None
    automator._verify_portal_entry_visible = lambda: True
    automator._wait_for_selector = lambda selector_key, timeout=None: FakeLocator()

    automator._open_login_page()

    assert fake_page.goto_url == config.PORTAL_URL
    assert fake_page.goto_wait_until == "commit"
    assert fake_page.goto_timeout == config.PAGE_LOAD_TIMEOUT
    assert fake_page.wait_for_url_called
    assert fake_page.wait_for_url_pattern == "**/devp/siap/signin.php"


def test_portal_navigation_retries_after_initial_timeout(monkeypatch):
    automator = SimpegAutomator("user", "pass", show_browser=False, dry_run=True)
    fake_page = FakePage()
    fake_page.timeout_on_attempts = {1}
    automator.page = fake_page
    automator._set_state = lambda state: None
    automator._update_status = lambda message: None
    automator._click_selector = lambda selector_key: None
    verify_calls = [False, True]

    def staged_verify():
        return verify_calls.pop(0)

    automator._verify_portal_entry_visible = staged_verify
    automator._wait_for_selector = lambda selector_key, timeout=None: FakeLocator()

    automator._open_login_page()

    assert fake_page.request_count == 2
    assert fake_page.goto_url == config.PORTAL_URL


def test_portal_timeout_but_existing_portal_visible(monkeypatch):
    automator = SimpegAutomator("user", "pass", show_browser=False, dry_run=True)
    fake_page = FakePage()
    fake_page.force_timeout = True
    automator.page = fake_page
    automator._set_state = lambda state: None
    automator._update_status = lambda message: None
    automator._click_selector = lambda selector_key: None
    automator._verify_portal_entry_visible = lambda: True
    automator._wait_for_selector = lambda selector_key, timeout=None: FakeLocator()

    automator._open_login_page()

    assert fake_page.request_count == 1
    assert fake_page.goto_url == config.PORTAL_URL


def test_portal_navigation_fails_after_all_retries(monkeypatch):
    automator = SimpegAutomator("user", "pass", show_browser=False, dry_run=True)
    fake_page = FakePage()
    fake_page.force_timeout = True
    automator.page = fake_page
    automator._set_state = lambda state: None
    automator._update_status = lambda message: None
    automator._click_selector = lambda selector_key: None
    automator._verify_portal_entry_visible = lambda: False
    automator._wait_for_selector = lambda selector_key, timeout=None: FakeLocator()

    saved = {}

    def fake_save_debug_artifacts(prefix, summary):
        saved["prefix"] = prefix
        saved["summary"] = summary

    automator._save_debug_artifacts = fake_save_debug_artifacts

    with pytest.raises(Exception, match="Gagal membuka portal SIMPEG"):
        automator._open_login_page()

    assert saved["prefix"] == "portal-navigation-failed"


def test_browser_cleanup_after_login_failure(monkeypatch):
    automator = SimpegAutomator("user", "pass", show_browser=False, dry_run=True)
    automator._set_state = lambda state: None
    automator._update_status = lambda message: None

    class FakeContext:
        def __init__(self):
            self.closed = False
        def new_page(self):
            return FakePage()
        def close(self):
            self.closed = True

    class FakeBrowser:
        def __init__(self):
            self.closed = False
            self.context = FakeContext()
        def new_context(self):
            return self.context
        def close(self):
            self.closed = True

    class FakeChromium:
        def launch(self, headless=False):
            return FakeBrowser()

    class FakePlaywright:
        def __init__(self):
            self.chromium = FakeChromium()
            self.stopped = False
        def start(self):
            return self
        def stop(self):
            self.stopped = True

    fake_playwright = FakePlaywright()
    monkeypatch.setattr(automation, "sync_playwright", lambda: fake_playwright)
    monkeypatch.setattr(automation, "load_journal_template", lambda: [{
        "start_hour": "07",
        "end_hour": "16",
        "activity_description": "desc",
        "completion_value": "1",
    }])
    monkeypatch.setattr(config, "TEMPLATE_FILE", config.TEMPLATE_FILE)
    automator._perform_login = lambda: (_ for _ in ()).throw(LoginError("fail"))
    closed = {"called": False}
    automator.close_browser = lambda: closed.__setitem__("called", True)

    with pytest.raises(LoginError):
        automator.run()

    assert closed["called"] is True


def test_template_requires_skp_category(tmp_path):
    path = tmp_path / "journal_template.json"
    data = [
        {
            "start_hour": "08",
            "start_minute": "00",
            "end_hour": "16",
            "end_minute": "30",
            "activity_description": "Pelaksanaan layanan IT",
            "completion_value": "0",
        }
    ]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(Exception, match="field 'skp_category'"):
        template_loader.load_journal_template(path)


def test_optional_minute_fields_are_skipped_when_selectors_are_unavailable(monkeypatch):
    monkeypatch.setitem(config.SELECTORS, "start_minute", None)
    monkeypatch.setitem(config.SELECTORS, "end_minute", None)
    automator = SimpegAutomator("user", "pass", show_browser=False, dry_run=True)
    automator._set_state = lambda state: None
    messages = []
    automator._update_status = lambda message: messages.append(message)
    automator.page = FakePage()

    locators = {
        "start_hour": FakeLocator(text="08"),
        "end_hour": FakeLocator(text="16"),
        "skp_category": FakeLocator(text=""),
        "activity_description": FakeLocator(text=""),
        "completion_value": FakeLocator(text=""),
    }

    automator._make_locator = lambda selector: locators[
        {
            config.SELECTORS["start_hour"]: "start_hour",
            config.SELECTORS["end_hour"]: "end_hour",
            config.SELECTORS["skp_category"]: "skp_category",
            config.SELECTORS["activity_description"]: "activity_description",
            config.SELECTORS["completion_value"]: "completion_value",
        }[selector]
    ]
    automator._get_locator_by_label_or_selector = lambda selector_key, label_text=None: locators.get(selector_key, FakeLocator(text=""))

    data = {
        "start_hour": "08",
        "start_minute": "00",
        "end_hour": "16",
        "end_minute": "30",
        "skp_category": "Lain-lain",
        "activity_description": "Pelaksanaan layanan IT",
        "completion_value": "0",
    }
    automator.template = [data]

    automator._fill_journal_entries()

    assert "Selector menit mulai belum diverifikasi; field dilewati." in messages
    assert "Selector menit selesai belum diverifikasi; field dilewati." in messages
    assert locators["start_hour"].selected == "08"
    assert locators["end_hour"].selected == "16"


def test_production_blocks_when_minute_selectors_are_missing(monkeypatch):
    monkeypatch.setitem(config.SELECTORS, "start_minute", None)
    monkeypatch.setitem(config.SELECTORS, "end_minute", None)
    automator = SimpegAutomator("user", "pass", show_browser=False, dry_run=False)
    automator._set_state = lambda state: None
    automator._update_status = lambda message: None
    automator.page = FakePage()

    locators = {
        "start_hour": FakeLocator(text="08"),
        "end_hour": FakeLocator(text="16"),
        "skp_category": FakeLocator(text=""),
        "activity_description": FakeLocator(text=""),
        "completion_value": FakeLocator(text=""),
    }

    automator._make_locator = lambda selector: locators[
        {
            config.SELECTORS["start_hour"]: "start_hour",
            config.SELECTORS["end_hour"]: "end_hour",
            config.SELECTORS["skp_category"]: "skp_category",
            config.SELECTORS["activity_description"]: "activity_description",
            config.SELECTORS["completion_value"]: "completion_value",
        }[selector]
    ]
    automator._get_locator_by_label_or_selector = lambda selector_key, label_text=None: locators.get(selector_key, FakeLocator(text=""))

    data = {
        "start_hour": "08",
        "start_minute": "00",
        "end_hour": "16",
        "end_minute": "30",
        "skp_category": "Lain-lain",
        "activity_description": "Pelaksanaan layanan IT",
        "completion_value": "0",
    }
    automator.template = [data]

    with pytest.raises(JournalEntryError, match="Field menit belum terverifikasi. Pengiriman jurnal dibatalkan."):
        automator._fill_journal_entries()


def test_skp_dropdown_selects_by_visible_label_and_verifies(monkeypatch):
    automator = SimpegAutomator("user", "pass", show_browser=False, dry_run=True)
    automator._set_state = lambda state: None
    automator._update_status = lambda message: None
    automator.page = FakePage()

    locators = {
        "start_hour": FakeLocator(text="08"),
        "start_minute": FakeLocator(text="00"),
        "end_hour": FakeLocator(text="16"),
        "end_minute": FakeLocator(text="30"),
        "skp_category": FakeLocator(text=""),
        "activity_description": FakeLocator(text=""),
        "completion_value": FakeLocator(text=""),
    }

    automator._make_locator = lambda selector: locators[{
        config.SELECTORS["start_hour"]: "start_hour",
        config.SELECTORS["start_minute"]: "start_minute",
        config.SELECTORS["end_hour"]: "end_hour",
        config.SELECTORS["end_minute"]: "end_minute",
        config.SELECTORS["skp_category"]: "skp_category",
        config.SELECTORS["activity_description"]: "activity_description",
        config.SELECTORS["completion_value"]: "completion_value",
    }[selector]] if selector in {
        config.SELECTORS["start_hour"]: "start_hour",
        config.SELECTORS["start_minute"]: "start_minute",
        config.SELECTORS["end_hour"]: "end_hour",
        config.SELECTORS["end_minute"]: "end_minute",
        config.SELECTORS["skp_category"]: "skp_category",
        config.SELECTORS["activity_description"]: "activity_description",
        config.SELECTORS["completion_value"]: "completion_value",
    } else locators["skp_category"]
    automator._get_locator_by_label_or_selector = lambda selector_key, label_text=None: locators.get(selector_key, FakeLocator(text=""))

    data = {
        "start_hour": "08",
        "start_minute": "00",
        "end_hour": "16",
        "end_minute": "30",
        "skp_category": "Lain-lain",
        "activity_description": "Pelaksanaan layanan IT",
        "completion_value": "0",
    }
    automator.template = [data]

    automator._fill_journal_entries()

    assert locators["skp_category"].selected == "Lain-lain"
    assert locators["skp_category"].text == "Lain-lain"
    assert locators["completion_value"].filled == "0"
    assert locators["start_hour"].selected == "08"
    assert locators["skp_category"].filled == "Lain-lain"


def test_incorrect_skp_selection_prevents_submission(monkeypatch):
    automator = SimpegAutomator("user", "pass", show_browser=False, dry_run=True)
    automator._set_state = lambda state: None
    automator._update_status = lambda message: None
    automator.page = FakePage()

    locators = {
        "start_hour": FakeLocator(text="08"),
        "start_minute": FakeLocator(text="00"),
        "end_hour": FakeLocator(text="16"),
        "end_minute": FakeLocator(text="30"),
        "skp_category": FakeLocator(text=""),
        "activity_description": FakeLocator(text="Pelaksanaan layanan IT"),
        "completion_value": FakeLocator(text="0"),
    }

    def bad_skp_select_option(value=None, label=None, timeout=None):
        locators["skp_category"].selected = "Lain-lain"
        locators["skp_category"].filled = "Lain-lain"
        locators["skp_category"].text = "Lain-lain"
        return None

    locators["skp_category"].select_option = bad_skp_select_option
    locators["skp_category"].locator = lambda selector: FakeLocator(text="Bukan Lain-lain")
    locators["skp_category"].element_handles = lambda: []

    automator._get_locator_by_label_or_selector = lambda selector_key, label_text=None: locators.get(selector_key, FakeLocator(text=""))
    automator._make_locator = lambda selector: locators[
        {
            config.SELECTORS["start_hour"]: "start_hour",
            config.SELECTORS["start_minute"]: "start_minute",
            config.SELECTORS["end_hour"]: "end_hour",
            config.SELECTORS["end_minute"]: "end_minute",
            config.SELECTORS["skp_category"]: "skp_category",
            config.SELECTORS["activity_description"]: "activity_description",
            config.SELECTORS["completion_value"]: "completion_value",
        }[selector]
    ]

    saved = {}
    automator._save_debug_artifacts = lambda prefix, summary: saved.update({"prefix": prefix, "summary": summary})

    data = {
        "start_hour": "08",
        "start_minute": "00",
        "end_hour": "16",
        "end_minute": "30",
        "skp_category": "Lain-lain",
        "activity_description": "Pelaksanaan layanan IT",
        "completion_value": "0",
    }
    automator.template = [data]

    with pytest.raises(JournalEntryError, match='Pilihan SKP gagal diubah menjadi "Lain-lain"'):
        automator._fill_journal_entries()
    assert saved.get("prefix") == "skp-category-mismatch"
    assert "Bukan Lain-lain" in saved.get("summary", "")


def test_manual_captcha_fallback_keeps_browser_open(monkeypatch):
    automator = SimpegAutomator("user", "pass", show_browser=False, dry_run=True)
    fake_page = FakePage()
    automator.page = fake_page
    automator._set_state = lambda state: None
    messages = []
    automator._update_status = lambda message: messages.append(message)
    automator._wait_for_login_result = lambda timeout: True

    monkeypatch.setitem(config.SELECTORS, "captcha_input", "role:textbox|name:Masukkan jawaban")
    monkeypatch.setitem(config.SELECTORS, "password_input", "css:#vpassword")
    fake_page.get_by_label = lambda label_text: FakeLocator()

    automator._fill_login_step2()

    assert any("Silakan isi captcha" in m for m in messages)
    assert fake_page.url == ""


def test_login_continues_after_authenticated_marker(monkeypatch):
    automator = SimpegAutomator("user", "pass", show_browser=False, dry_run=True)
    automator.page = FakePage()
    automator._set_state = lambda state: None
    automator._update_status = lambda message: None
    automator._make_locator = lambda selector: FakeLocator()

    def wait_for_selector(selector_key, timeout=None):
        if selector_key == "kinerja_menu":
            return FakeLocator()
        raise PlaywrightTimeoutError("missing")

    automator._wait_for_selector = wait_for_selector
    assert automator._wait_for_login_result(1000) is True


def test_captcha_and_credentials_are_not_logged(monkeypatch):
    captured = []
    automator = SimpegAutomator("1234567890", "secret-password", show_browser=False, dry_run=True)
    automator.page = FakePage()
    automator._set_state = lambda state: None
    automator._update_status = lambda message: captured.append(message)
    automator._wait_for_login_result = lambda timeout: True

    monkeypatch.setitem(config.SELECTORS, "password_input", "css:#vpassword")
    monkeypatch.setitem(config.SELECTORS, "captcha_input", "role:textbox|name:Masukkan jawaban")
    automator._make_locator = lambda selector: FakeLocator()
    automator._fill_login_step2()

    logged = " ".join(captured)
    assert "1234567890" not in logged
    assert "secret-password" not in logged
    assert "88" not in logged
    assert "cookie" not in logged.lower()
    assert "token" not in logged.lower()
    assert "session" not in logged.lower()
    assert "Masukkan jawaban" not in logged


from ui import RunGuard, request_automation_start


def test_production_requires_confirmation():
    guard = RunGuard()
    started = {"count": 0}

    def start_callback():
        started["count"] += 1

    result = request_automation_start(
        dry_run=False,
        confirmation_callback=lambda: True,
        start_callback=start_callback,
        run_guard=guard,
    )

    assert result is True
    assert guard.running is True
    assert started["count"] == 1


def test_production_cancel_confirmation_prevents_automation():
    guard = RunGuard()
    started = {"count": 0}

    def start_callback():
        started["count"] += 1

    result = request_automation_start(
        dry_run=False,
        confirmation_callback=lambda: False,
        start_callback=start_callback,
        run_guard=guard,
    )

    assert result is False
    assert guard.running is False
    assert started["count"] == 0

    second_result = request_automation_start(
        dry_run=False,
        confirmation_callback=lambda: True,
        start_callback=start_callback,
        run_guard=guard,
    )

    assert second_result is True
    assert guard.running is True
    assert started["count"] == 1


def test_dry_run_skips_confirmation_and_starts_directly():
    guard = RunGuard()
    started = {"count": 0}

    def start_callback():
        started["count"] += 1

    def confirmation_callback():
        raise AssertionError("Confirmation callback should not be called during dry run")

    result = request_automation_start(
        dry_run=True,
        confirmation_callback=confirmation_callback,
        start_callback=start_callback,
        run_guard=guard,
    )

    assert result is True
    assert guard.running is True
    assert started["count"] == 1


def test_duplicate_detection_unavailable_logs_not_performed(monkeypatch):
    monkeypatch.setitem(config.SELECTORS, "journal_table_rows", None)
    automator = SimpegAutomator("user", "pass", show_browser=False, dry_run=False)
    automator.page = FakePage()
    automator.template = [{
        "start_hour": "07",
        "end_hour": "16",
        "activity_description": "desc",
        "completion_value": "1",
    }]
    automator._set_state = lambda state: None
    automator._update_status = lambda message: None

    assert automator._detect_duplicate_journal() is False
    assert automator._duplicate_detection_available is False


def test_duplicate_journal_prevents_submission(monkeypatch):
    automator = SimpegAutomator("user", "pass", show_browser=False, dry_run=False)
    automator.page = FakePage()
    automator.template = [{
        "start_hour": "07",
        "end_hour": "16",
        "activity_description": "desc",
        "completion_value": "1",
    }]
    automator._set_state = lambda state: None
    automator._update_status = lambda message: None

    monkeypatch.setitem(config.SELECTORS, "journal_table_rows", "css:.row")
    monkeypatch.setitem(config.SELECTORS, "journal_row_description", "css:.desc")
    monkeypatch.setitem(config.SELECTORS, "journal_row_start_hour", "css:.start")
    monkeypatch.setitem(config.SELECTORS, "journal_row_end_hour", "css:.end")

    def fake_make_locator(selector):
        mapping = {
            config.SELECTORS["journal_table_rows"]: FakeLocator(),
            config.SELECTORS["journal_row_description"]: FakeLocator(text="desc"),
            config.SELECTORS["journal_row_start_hour"]: FakeLocator(text="07"),
            config.SELECTORS["journal_row_end_hour"]: FakeLocator(text="16"),
        }
        return mapping[selector]

    # Make the row locator return a row object for nth() that has nested locators.
    row = FakeLocator()
    row.locator = lambda selector: fake_make_locator(selector)
    rows = FakeLocator()
    rows.nth = lambda index: row
    rows.count = lambda: 1

    def fake_make_locator_with_rows(selector):
        if selector == config.SELECTORS["journal_table_rows"]:
            return rows
        return fake_make_locator(selector)

    automator._make_locator = fake_make_locator_with_rows

    assert automator._detect_duplicate_journal() is True


def test_duplicate_journal_negative_single_field_difference(monkeypatch):
    automator = SimpegAutomator("user", "pass", show_browser=False, dry_run=False)
    automator.page = FakePage()
    automator.template = [{
        "start_hour": "07",
        "end_hour": "16",
        "activity_description": "desc",
        "completion_value": "1",
    }]
    automator._set_state = lambda state: None
    automator._update_status = lambda message: None

    monkeypatch.setitem(config.SELECTORS, "journal_table_rows", "css:.row")
    monkeypatch.setitem(config.SELECTORS, "journal_row_description", "css:.desc")
    monkeypatch.setitem(config.SELECTORS, "journal_row_start_hour", "css:.start")
    monkeypatch.setitem(config.SELECTORS, "journal_row_end_hour", "css:.end")

    def fake_make_locator(selector):
        mapping = {
            config.SELECTORS["journal_table_rows"]: FakeLocator(),
            config.SELECTORS["journal_row_description"]: FakeLocator(text="desc"),
            config.SELECTORS["journal_row_start_hour"]: FakeLocator(text="08"),
            config.SELECTORS["journal_row_end_hour"]: FakeLocator(text="16"),
        }
        return mapping[selector]

    row = FakeLocator()
    row.locator = lambda selector: fake_make_locator(selector)
    rows = FakeLocator()
    rows.nth = lambda index: row
    rows.count = lambda: 1

    def fake_make_locator_with_rows(selector):
        if selector == config.SELECTORS["journal_table_rows"]:
            return rows
        return fake_make_locator(selector)

    automator._make_locator = fake_make_locator_with_rows

    assert automator._detect_duplicate_journal() is False


def test_duplicate_detection_with_empty_rows(monkeypatch):
    automator = SimpegAutomator("user", "pass", show_browser=False, dry_run=False)
    automator.page = FakePage()
    automator.template = [{
        "start_hour": "07",
        "end_hour": "16",
        "activity_description": "desc",
        "completion_value": "1",
    }]
    automator._set_state = lambda state: None
    automator._update_status = lambda message: None

    monkeypatch.setitem(config.SELECTORS, "journal_table_rows", "css:.row")
    monkeypatch.setitem(config.SELECTORS, "journal_row_description", "css:.desc")
    monkeypatch.setitem(config.SELECTORS, "journal_row_start_hour", "css:.start")
    monkeypatch.setitem(config.SELECTORS, "journal_row_end_hour", "css:.end")

    rows = FakeLocator()
    rows.count = lambda: 0

    automator._make_locator = lambda selector: rows if selector == config.SELECTORS["journal_table_rows"] else FakeLocator(text="")

    assert automator._detect_duplicate_journal() is False


def test_prevents_double_run(monkeypatch):
    from ui import RunGuard

    guard = RunGuard()
    assert guard.start() is True
    assert guard.running is True
    assert guard.start() is False
    guard.stop()
    assert guard.running is False
