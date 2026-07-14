// @ts-check
import { test, expect } from '@playwright/test';

// Tests for the dummy-app (../dummy-app relative to this project), which lives
// at http://localhost:5173 (see baseURL in playwright.config.js).
test.describe('Dummy App Auth Flow', () => {

  test('Valid Login', async ({ page }) => {
    // Go to the login page and submit the hardcoded valid credentials.
    await page.goto('/');
    await page.getByTestId('email-input').fill('admin@test.com');
    await page.getByTestId('password-input').fill('1234');
    await page.getByTestId('login-button').click();

    // A successful login should redirect to /home and show the welcome message.
    await expect(page).toHaveURL(/\/home$/);
    await expect(page.getByTestId('welcome-message')).toBeVisible();
  });

  test('Invalid Login', async ({ page }) => {
    // Submit credentials that don't match the hardcoded admin account.
    await page.goto('/');
    await page.getByTestId('email-input').fill('wrong@test.com');
    await page.getByTestId('password-input').fill('wrong');
    await page.getByTestId('login-button').click();

    // The app should stay on the login page and surface an error message.
    await expect(page.getByTestId('error-message')).toBeVisible();
    await expect(page.getByTestId('error-message')).toContainText('Invalid credentials');
  });

  test('Logout', async ({ page }) => {
    // Log in first so we land on the protected /home page.
    await page.goto('/');
    await page.getByTestId('email-input').fill('admin@test.com');
    await page.getByTestId('password-input').fill('1234');
    await page.getByTestId('login-button').click();
    await expect(page).toHaveURL(/\/home$/);

    // Logging out should clear the session and send the user back to the login page.
    await page.getByTestId('logout-button').click();
    await expect(page).toHaveURL(/\/$/);
  });

  test('Open Profile', async ({ page }) => {
    // Log in first so we land on the protected /home page.
    await page.goto('/');
    await page.getByTestId('email-input').fill('admin@test.com');
    await page.getByTestId('password-input').fill('1234');
    await page.getByTestId('login-button').click();
    await expect(page).toHaveURL(/\/home$/);

    // Navigating to the profile page should show the static dummy profile info.
    await page.getByTestId('profile-link').click();
    await expect(page).toHaveURL(/\/profile$/);
    await expect(page.getByTestId('profile-name')).toBeVisible();
    await expect(page.getByTestId('profile-name')).toContainText('Test User');
  });

});
