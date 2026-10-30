/**
 * Інструмент: Antigravity
 * Застосування: Написання e2e тесту додавання посилань використовуючи playwright
 * Верифікація: Перевірено код, результат в playwright ui та логіку
 */

import { test, expect } from '@playwright/test';

const TEST_BOARD_ID = '881c9ea7-0d0c-4864-bafe-fbcb2bf70722';

test.describe('TP-12: Продуктивність збереження посилань', () => {
  let accessToken: string;

  test.beforeEach(async ({ page, request }) => {
    const loginRes = await request.post('http://localhost:3000/v1/auth/login', {
      data: { email: 'e2e@example.com', password: '12345678' }
    });
    accessToken = (await loginRes.json()).access_token;

    const cardsRes = await request.get(`http://localhost:3000/v1/boards/${TEST_BOARD_ID}/cards`, {
      headers: { Authorization: `Bearer ${accessToken}` }
    });
    const cards = await cardsRes.json();

    if (cards.items.length === 0) {
      const stagesRes = await request.get(`http://localhost:3000/v1/boards/${TEST_BOARD_ID}/stages`, {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      const stageId = (await stagesRes.json())[0].id;

      await request.post(`http://localhost:3000/v1/boards/${TEST_BOARD_ID}/cards`, {
        data: { stage_id: stageId, company: 'Perf Test Co', position: 'Engineer' },
        headers: { Authorization: `Bearer ${accessToken}` }
      });
    }

    await page.goto('http://localhost:5173/');
    await page.fill('input[type="email"]', 'e2e@example.com');
    await page.fill('input[type="password"]', '12345678');
    await page.click('button:has-text("Увійти")');

    await page.fill('input[placeholder="3fa85f64-5717-4562-b3fc-2c963f66afa6"]', TEST_BOARD_ID);
    await page.click('button:has-text("Відкрити дошку")');

    const card = page.locator('.card-item').first();
    await card.waitFor({ state: 'visible' });
    await card.click();
    await expect(page.locator('.modal-card')).toBeVisible();
  });

  test.afterEach(async ({ request }) => {
    if (accessToken) {
      const cards = await (await request.get(`http://localhost:3000/v1/boards/${TEST_BOARD_ID}/cards`, {
        headers: { Authorization: `Bearer ${accessToken}` }
      })).json();
      
      for (const card of cards.items) {
        await request.delete(`http://localhost:3000/v1/boards/${TEST_BOARD_ID}/cards/${card.id}`, {
          headers: { Authorization: `Bearer ${accessToken}` }
        });
      }
    }
  });

  test('Додавання посилання має вкладатися в 300мс (TP-12)', async ({ page }) => {
    const input = page.locator('.modal-section form.inline-form input[type="url"]').first();
    const btn = page.locator('.modal-section form.inline-form button[type="submit"]').first();
    const durations: number[] = [];
    for (let i = 1; i <= 30; i++) {
      const url = `https://example.com/perf-${i}`;
      await input.fill(url);
      
      const start = performance.now();
      await btn.click();
      await expect(page.locator('.simple-list a', { hasText: url })).toBeVisible();
      const duration = performance.now() - start;
      durations.push(duration);
      expect(duration).toBeLessThanOrEqual(300);
    }
    const totalDuration = durations.reduce((sum, current) => sum + current, 0);
    const avgDuration = totalDuration / durations.length;
    const maxDuration = Math.max(...durations);

    console.log(`\n--- Результати тесту продуктивності (TP-12) ---`);
    console.log(`Кількість ітерацій: ${durations.length}`);
    console.log(`Середній час: ${avgDuration.toFixed(2)} мс`);
    console.log(`Максимальний час: ${maxDuration.toFixed(2)} мс`);

    expect(avgDuration).toBeLessThanOrEqual(300);
  });
});