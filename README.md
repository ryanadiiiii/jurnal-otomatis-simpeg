# SIMPEG Daily Journal Automation

A Python desktop application using CustomTkinter and Playwright to automate the Indonesian Ministry of Law employee daily journal (SIMPEG) submission process.

## Main features

- Modern desktop GUI with login form and progress status
- Playwright browser automation for login and journal submission
- EasyOCR captcha recognition with manual fallback
- Template-driven daily journal filling using `journal_template.json`
- Dry-run mode enabled by default to prevent accidental submission
- Logging and debug artifact saving
- Clean project structure with separate modules and validation

## Recommended Python version

- Python 3.11 or newer is recommended.

## Windows setup

```powershell
cd "d:\CODING\Jurnal Harian Otomatis"
py -m venv .venv
.venv\Scripts\Activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

## Dependency installation

Install required packages with:

```powershell
python -m pip install -r requirements.txt
```

Then install Chromium for Playwright:

```powershell
python -m playwright install chromium
```

## Running the application

Start the desktop app with:

```powershell
python main.py
```

## Editing the journal template

The journal template is stored in `journal_template.json`.
Update the `task`, `status`, and `notes` fields for each entry.

## Log and debug files

- Log file: `simpeg_journal.log`
- Debug artifacts: `debug/`

> Security warning: debug screenshots and HTML files may contain sensitive UI content. Do not commit `debug/` to Git or share these files publicly.

## Captcha handling

- The app will first try to solve the captcha automatically using EasyOCR.
- If OCR fails, the app keeps the browser open and prompts manual captcha entry.
- Manual captcha entry must be completed in the browser window before the timeout expires.

## Security notes

- Do not store passwords or real credentials in source files.
- The app does not log passwords, cookies, session IDs, authentication tokens, or authorization headers.
- Debug artifacts include screenshots, HTML, and URL state. Treat `debug/` as sensitive data and do not commit it.

## Troubleshooting

- Verify `journal_template.json` is valid JSON.
- Verify selectors in `config.py` if the SIMPEG website layout has changed.
- If Playwright fails to start, run `python -m playwright install chromium`.

## Testing

Run tests with:

```powershell
pytest
```

## Selector verification workflow

1. Run `playwright codegen https://simpeg.kemenkum.go.id/`
2. Inspect the portal homepage and open the `SIMPEG HUKUM` tile.
3. Inspect the NIP input selector.
4. Inspect the `Masuk` button selector.
5. Inspect the password input selector.
6. Inspect the captcha input selector.
7. Inspect the login button selector.
8. Complete login manually in the browser.
9. Inspect a reliable dashboard marker or logout button.
10. Navigate to `KINERJA` and then `Jurnal Harian`.
11. Inspect the `Tambah` link selector.
12. Inspect the verified journal fields:
    - `#jammulai`
    - `#jamselesai`
    - `#keterangan`
    - `#satuan`
13. Inspect the `Simpan` button selector.
14. Inspect the success notification selector.

Update all verified selectors only in `config.py`.
