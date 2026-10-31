/**
 * Інструмент: Claude
 * Застосування: Спільна підготовка e2e-сесії — вхід (або реєстрація на
 * чистій базі) тестового кандидата і board_id з GET /v1/boards замість
 * зашитого в тести ідентифікатора.
 * Верифікація: Прогін обох спеків проти API з PostgreSQL і Vite dev-сервера.
 */

import { expect, type APIRequestContext, type Page } from '@playwright/test';

export const API_URL = process.env.E2E_API_URL ?? 'http://localhost:3000';
export const UI_URL = process.env.E2E_UI_URL ?? 'http://localhost:5173';
export const EMAIL = process.env.E2E_EMAIL ?? 'e2e@example.com';
export const PASSWORD = process.env.E2E_PASSWORD ?? '12345678';

export interface Session {
  headers: Record<string, string>;
  boardId: string;
}

// Реєструє кандидата, якщо його ще немає, тож тести не потребують
// підготовленої вручну бази.
export async function apiSession(request: APIRequestContext): Promise<Session> {
  let auth = await request.post(`${API_URL}/v1/auth/login`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  if (auth.status() === 401) {
    auth = await request.post(`${API_URL}/v1/auth/register`, {
      data: { email: EMAIL, password: PASSWORD, role: 'candidate' },
    });
  }
  expect(auth.ok()).toBeTruthy();
  const headers = { Authorization: `Bearer ${(await auth.json()).access_token}` };

  const boards = await (await request.get(`${API_URL}/v1/boards`, { headers })).json();
  const own = boards.find((board: { access: string }) => board.access === 'owner');
  expect(own, `${EMAIL} не має власної дошки`).toBeTruthy();
  return { headers, boardId: own.id };
}

// Кандидат має одну дошку, і /board/setup відкриває її сам після входу.
export async function openBoard(page: Page) {
  await page.goto(UI_URL);
  await page.fill('input[type="email"]', EMAIL);
  await page.fill('input[type="password"]', PASSWORD);
  await page.click('button:has-text("Увійти")');
  await page.locator('.stage-column').first().waitFor();
}
