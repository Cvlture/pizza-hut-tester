# NZ Pizza Hut Tester

A Windows-friendly Tkinter control panel for running the Pizza Hut browser workflow with Playwright.

## Requirements

- Python 3.10 or newer
- Playwright for Python
- Playwright Chromium browser

Install the dependency with:

```powershell
python -m pip install playwright
python -m playwright install chromium
```

## Run

From the project folder:

```powershell
python app.py
```

The app opens the settings window and keeps it available while the browser session is running.

## Workflow

1. Configure the Pizza Hut URL, code count, browser profile, and viewport size.
2. Enable headless mode only when you want to use the configured coupons URL automatically.
3. Click **Open Browser**.
4. In headed mode, choose the location and add items to the cart.
5. When the coupon field is visible, click **Start Testing** in the app.
6. Monitor attempts in the progress console.
7. Use **Pause**, **Resume**, **Cancel**, or **Close Browser** as needed.

The tester generates randomized five-digit codes divisible by three, using the configured code count. Use it only with accounts, carts, and testing activity you are authorized to operate.

## Settings

Settings are saved locally to `pizza_settings.json` after a session starts. That file is intentionally ignored by Git because it contains machine-specific preferences.

Use **Reset** to restore the default settings. Use **Export Log** to save the current console output as a timestamped text file.

## Browser profile

The persistent Chromium profile is stored in `pizza_profile/` so browser cookies and selections can survive between sessions. Close other Chromium sessions using the same profile before opening a new one.

The profile directory and generated settings are excluded from version control.
