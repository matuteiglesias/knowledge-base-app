import { test, expect } from '@playwright/test';

test('health/papers page smoke', async ({ page }) => {
  await page.goto('http://localhost:3000/health/papers', { waitUntil: 'domcontentloaded' });
  // either shows 'No papers' or at least the papers container
  const noPapers = await page.locator('text=No papers').count();
  expect(noPapers + await page.locator('[data-testid="paper-list"]').count()).toBeGreaterThan(0);
});
