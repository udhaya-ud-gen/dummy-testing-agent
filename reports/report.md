# Playwright Test Report

- **Timestamp:** 2026-07-14T06:31:24.955146+00:00
- **Total tests:** 12
- **Passed:** 0
- **Failed:** 12

## Failures

### 1. Valid Login (chromium)

- **Error:** Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByTestId('login-button')


  11 |     await page.getByTestId('email-input').fill('admin@test.com');
  12 |     await page.getByTestId('password-input').fill('1234');
> 13 |     await page.getByTestId('login-button').click();
     |                                            ^
  14 |
  15 |     // A successful login should redirect to /home and show the welcome message.
  16 |     await expect(page).toHaveURL(/\/... (truncated)
- **Root cause:** Likely a selector/data-testid mismatch, or the element never rendered in time (app crash, slow network, wrong route, etc.).
- **Severity:** high
- **Confidence:** 75%
- **Suggested fix:** Check whether the element's data-testid or selector changed in the app code, and confirm the page actually reaches the expected state before the timeout elapses.
- **Screenshot:** [test-results/auth-Dummy-App-Auth-Flow-Valid-Login-chromium/test-failed-1.png](test-results/auth-Dummy-App-Auth-Flow-Valid-Login-chromium/test-failed-1.png)

### 2. Invalid Login (chromium)

- **Error:** Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByTestId('login-button')


  23 |     await page.getByTestId('email-input').fill('wrong@test.com');
  24 |     await page.getByTestId('password-input').fill('wrong');
> 25 |     await page.getByTestId('login-button').click();
     |                                            ^
  26 |
  27 |     // The app should stay on the login page and surface an error message.
  28 |     await expect(page.getByTestId('error-... (truncated)
- **Root cause:** Likely a selector/data-testid mismatch, or the element never rendered in time (app crash, slow network, wrong route, etc.).
- **Severity:** high
- **Confidence:** 75%
- **Suggested fix:** Check whether the element's data-testid or selector changed in the app code, and confirm the page actually reaches the expected state before the timeout elapses.
- **Screenshot:** [test-results/auth-Dummy-App-Auth-Flow-Invalid-Login-chromium/test-failed-1.png](test-results/auth-Dummy-App-Auth-Flow-Invalid-Login-chromium/test-failed-1.png)

### 3. Logout (chromium)

- **Error:** Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByTestId('login-button')


  35 |     await page.getByTestId('email-input').fill('admin@test.com');
  36 |     await page.getByTestId('password-input').fill('1234');
> 37 |     await page.getByTestId('login-button').click();
     |                                            ^
  38 |     await expect(page).toHaveURL(/\/home$/);
  39 |
  40 |     // Logging out should clear the session and send the user back to th... (truncated)
- **Root cause:** Likely a selector/data-testid mismatch, or the element never rendered in time (app crash, slow network, wrong route, etc.).
- **Severity:** high
- **Confidence:** 75%
- **Suggested fix:** Check whether the element's data-testid or selector changed in the app code, and confirm the page actually reaches the expected state before the timeout elapses.
- **Screenshot:** [test-results/auth-Dummy-App-Auth-Flow-Logout-chromium/test-failed-1.png](test-results/auth-Dummy-App-Auth-Flow-Logout-chromium/test-failed-1.png)

### 4. Open Profile (chromium)

- **Error:** Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByTestId('login-button')


  48 |     await page.getByTestId('email-input').fill('admin@test.com');
  49 |     await page.getByTestId('password-input').fill('1234');
> 50 |     await page.getByTestId('login-button').click();
     |                                            ^
  51 |     await expect(page).toHaveURL(/\/home$/);
  52 |
  53 |     // Navigating to the profile page should show the static dummy profi... (truncated)
- **Root cause:** Likely a selector/data-testid mismatch, or the element never rendered in time (app crash, slow network, wrong route, etc.).
- **Severity:** high
- **Confidence:** 75%
- **Suggested fix:** Check whether the element's data-testid or selector changed in the app code, and confirm the page actually reaches the expected state before the timeout elapses.
- **Screenshot:** [test-results/auth-Dummy-App-Auth-Flow-Open-Profile-chromium/test-failed-1.png](test-results/auth-Dummy-App-Auth-Flow-Open-Profile-chromium/test-failed-1.png)

### 5. Valid Login (firefox)

- **Error:** Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByTestId('login-button')


  11 |     await page.getByTestId('email-input').fill('admin@test.com');
  12 |     await page.getByTestId('password-input').fill('1234');
> 13 |     await page.getByTestId('login-button').click();
     |                                            ^
  14 |
  15 |     // A successful login should redirect to /home and show the welcome message.
  16 |     await expect(page).toHaveURL(/\/... (truncated)
- **Root cause:** Likely a selector/data-testid mismatch, or the element never rendered in time (app crash, slow network, wrong route, etc.).
- **Severity:** high
- **Confidence:** 75%
- **Suggested fix:** Check whether the element's data-testid or selector changed in the app code, and confirm the page actually reaches the expected state before the timeout elapses.
- **Screenshot:** [test-results/auth-Dummy-App-Auth-Flow-Valid-Login-firefox/test-failed-1.png](test-results/auth-Dummy-App-Auth-Flow-Valid-Login-firefox/test-failed-1.png)

### 6. Invalid Login (firefox)

- **Error:** Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByTestId('login-button')


  23 |     await page.getByTestId('email-input').fill('wrong@test.com');
  24 |     await page.getByTestId('password-input').fill('wrong');
> 25 |     await page.getByTestId('login-button').click();
     |                                            ^
  26 |
  27 |     // The app should stay on the login page and surface an error message.
  28 |     await expect(page.getByTestId('error-... (truncated)
- **Root cause:** Likely a selector/data-testid mismatch, or the element never rendered in time (app crash, slow network, wrong route, etc.).
- **Severity:** high
- **Confidence:** 75%
- **Suggested fix:** Check whether the element's data-testid or selector changed in the app code, and confirm the page actually reaches the expected state before the timeout elapses.
- **Screenshot:** [test-results/auth-Dummy-App-Auth-Flow-Invalid-Login-firefox/test-failed-1.png](test-results/auth-Dummy-App-Auth-Flow-Invalid-Login-firefox/test-failed-1.png)

### 7. Logout (firefox)

- **Error:** Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByTestId('login-button')


  35 |     await page.getByTestId('email-input').fill('admin@test.com');
  36 |     await page.getByTestId('password-input').fill('1234');
> 37 |     await page.getByTestId('login-button').click();
     |                                            ^
  38 |     await expect(page).toHaveURL(/\/home$/);
  39 |
  40 |     // Logging out should clear the session and send the user back to th... (truncated)
- **Root cause:** Likely a selector/data-testid mismatch, or the element never rendered in time (app crash, slow network, wrong route, etc.).
- **Severity:** high
- **Confidence:** 75%
- **Suggested fix:** Check whether the element's data-testid or selector changed in the app code, and confirm the page actually reaches the expected state before the timeout elapses.
- **Screenshot:** [test-results/auth-Dummy-App-Auth-Flow-Logout-firefox/test-failed-1.png](test-results/auth-Dummy-App-Auth-Flow-Logout-firefox/test-failed-1.png)

### 8. Open Profile (firefox)

- **Error:** Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByTestId('login-button')


  48 |     await page.getByTestId('email-input').fill('admin@test.com');
  49 |     await page.getByTestId('password-input').fill('1234');
> 50 |     await page.getByTestId('login-button').click();
     |                                            ^
  51 |     await expect(page).toHaveURL(/\/home$/);
  52 |
  53 |     // Navigating to the profile page should show the static dummy profi... (truncated)
- **Root cause:** Likely a selector/data-testid mismatch, or the element never rendered in time (app crash, slow network, wrong route, etc.).
- **Severity:** high
- **Confidence:** 75%
- **Suggested fix:** Check whether the element's data-testid or selector changed in the app code, and confirm the page actually reaches the expected state before the timeout elapses.
- **Screenshot:** [test-results/auth-Dummy-App-Auth-Flow-Open-Profile-firefox/test-failed-1.png](test-results/auth-Dummy-App-Auth-Flow-Open-Profile-firefox/test-failed-1.png)

### 9. Valid Login (webkit)

- **Error:** Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByTestId('login-button')


  11 |     await page.getByTestId('email-input').fill('admin@test.com');
  12 |     await page.getByTestId('password-input').fill('1234');
> 13 |     await page.getByTestId('login-button').click();
     |                                            ^
  14 |
  15 |     // A successful login should redirect to /home and show the welcome message.
  16 |     await expect(page).toHaveURL(/\/... (truncated)
- **Root cause:** Likely a selector/data-testid mismatch, or the element never rendered in time (app crash, slow network, wrong route, etc.).
- **Severity:** high
- **Confidence:** 75%
- **Suggested fix:** Check whether the element's data-testid or selector changed in the app code, and confirm the page actually reaches the expected state before the timeout elapses.
- **Screenshot:** [test-results/auth-Dummy-App-Auth-Flow-Valid-Login-webkit/test-failed-1.png](test-results/auth-Dummy-App-Auth-Flow-Valid-Login-webkit/test-failed-1.png)

### 10. Invalid Login (webkit)

- **Error:** Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByTestId('login-button')


  23 |     await page.getByTestId('email-input').fill('wrong@test.com');
  24 |     await page.getByTestId('password-input').fill('wrong');
> 25 |     await page.getByTestId('login-button').click();
     |                                            ^
  26 |
  27 |     // The app should stay on the login page and surface an error message.
  28 |     await expect(page.getByTestId('error-... (truncated)
- **Root cause:** Likely a selector/data-testid mismatch, or the element never rendered in time (app crash, slow network, wrong route, etc.).
- **Severity:** high
- **Confidence:** 75%
- **Suggested fix:** Check whether the element's data-testid or selector changed in the app code, and confirm the page actually reaches the expected state before the timeout elapses.
- **Screenshot:** [test-results/auth-Dummy-App-Auth-Flow-Invalid-Login-webkit/test-failed-1.png](test-results/auth-Dummy-App-Auth-Flow-Invalid-Login-webkit/test-failed-1.png)

### 11. Logout (webkit)

- **Error:** Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByTestId('login-button')


  35 |     await page.getByTestId('email-input').fill('admin@test.com');
  36 |     await page.getByTestId('password-input').fill('1234');
> 37 |     await page.getByTestId('login-button').click();
     |                                            ^
  38 |     await expect(page).toHaveURL(/\/home$/);
  39 |
  40 |     // Logging out should clear the session and send the user back to th... (truncated)
- **Root cause:** Likely a selector/data-testid mismatch, or the element never rendered in time (app crash, slow network, wrong route, etc.).
- **Severity:** high
- **Confidence:** 75%
- **Suggested fix:** Check whether the element's data-testid or selector changed in the app code, and confirm the page actually reaches the expected state before the timeout elapses.
- **Screenshot:** [test-results/auth-Dummy-App-Auth-Flow-Logout-webkit/test-failed-1.png](test-results/auth-Dummy-App-Auth-Flow-Logout-webkit/test-failed-1.png)

### 12. Open Profile (webkit)

- **Error:** Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByTestId('login-button')


  48 |     await page.getByTestId('email-input').fill('admin@test.com');
  49 |     await page.getByTestId('password-input').fill('1234');
> 50 |     await page.getByTestId('login-button').click();
     |                                            ^
  51 |     await expect(page).toHaveURL(/\/home$/);
  52 |
  53 |     // Navigating to the profile page should show the static dummy profi... (truncated)
- **Root cause:** Likely a selector/data-testid mismatch, or the element never rendered in time (app crash, slow network, wrong route, etc.).
- **Severity:** high
- **Confidence:** 75%
- **Suggested fix:** Check whether the element's data-testid or selector changed in the app code, and confirm the page actually reaches the expected state before the timeout elapses.
- **Screenshot:** [test-results/auth-Dummy-App-Auth-Flow-Open-Profile-webkit/test-failed-1.png](test-results/auth-Dummy-App-Auth-Flow-Open-Profile-webkit/test-failed-1.png)
