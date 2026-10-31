/**
 * Інструмент: Claude
 * Застосування: Характеризаційні e2e-тести Lab08 – фіксують поточну поведінку
 * компонентів дошки (CardItem, CardModal, MentorsPanel, NewCardForm,
 * StageColumn) перед рефакторингом зауважень SonarQube S6848 і S9379.
 * Верифікація: Прогін у Chrome проти API з PostgreSQL на гілці pre-refactor
 * і після кожного кроку рефакторингу.
 *
 * Як і test_performance.spec.ts, потребує запущених API та Vite dev-сервера;
 * тестового кандидата і його board_id готує e2e/session.ts. Адреси й
 * обліковий запис змінюються через змінні E2E_*.
 * Тести створюють власні картки і видаляють лише їх.
 */

import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import { API_URL, apiSession, openBoard } from './session';

const SURFACE = 'rgb(255, 255, 255)';

let headers: Record<string, string>;
let boardId: string;
let stageIds: string[];
let createdCardIds: string[];

async function createCard(request: APIRequestContext, name: string, stage = 0): Promise<string> {
  const company = `${name} ${Date.now()}`;
  const response = await request.post(`${API_URL}/v1/boards/${boardId}/cards`, {
    data: { stage_id: stageIds[stage], company, position: 'Engineer' },
    headers,
  });
  expect(response.status()).toBe(201);
  createdCardIds.push((await response.json()).id);
  return company;
}

async function stageOf(request: APIRequestContext, company: string): Promise<string> {
  const cards = await (
    await request.get(`${API_URL}/v1/boards/${boardId}/cards`, { headers })
  ).json();
  return cards.items.find((card: { company: string }) => card.company === company).stage_id;
}

const cardItem = (page: Page, company: string) => page.locator('.card-item', { hasText: company });
const modal = (page: Page) => page.locator('.modal-card');

test.describe('Lab08: поведінка дошки до і після рефакторингу', () => {
  test.beforeEach(async ({ request }) => {
    ({ headers, boardId } = await apiSession(request));
    const stages = await (
      await request.get(`${API_URL}/v1/boards/${boardId}/stages`, { headers })
    ).json();
    stageIds = stages.map((stage: { id: string }) => stage.id);
    createdCardIds = [];
  });

  test.afterEach(async ({ request }) => {
    for (const id of createdCardIds) {
      await request.delete(`${API_URL}/v1/boards/${boardId}/cards/${id}`, { headers });
    }
  });

  test('картка відкривається кліком; модалку закриває фон і ✕, але не клік усередині', async ({ page, request }) => {
    const company = await createCard(request, 'Modal Co');
    await openBoard(page);

    await cardItem(page, company).click();
    await expect(modal(page)).toBeVisible();
    await modal(page).locator('h2').click();
    await expect(modal(page)).toBeVisible();
    await page.mouse.click(10, 10);
    await expect(modal(page)).toHaveCount(0);

    await cardItem(page, company).click();
    await modal(page).locator('.modal-header button').click();
    await expect(modal(page)).toHaveCount(0);
  });

  test('клік по фону закриває модалку і після прокручування', async ({ page, request }) => {
    const company = await createCard(request, 'Scroll Co');
    await page.setViewportSize({ width: 1280, height: 400 });
    await openBoard(page);

    await cardItem(page, company).click();
    const overlay = page.locator('.modal-overlay');
    const scrolled = await overlay.evaluate((el) => {
      el.scrollTo(0, el.scrollHeight);
      return el.scrollTop;
    });
    expect(scrolled).toBeGreaterThan(0);
    await page.mouse.click(10, 390);
    await expect(modal(page)).toHaveCount(0);
  });

  test('панель менторів закриває клік по фону, але не клік усередині', async ({ page }) => {
    await openBoard(page);

    await page.click('button:has-text("Ментори")');
    await modal(page).locator('h2').click();
    await expect(modal(page)).toBeVisible();
    await page.mouse.click(10, 10);
    await expect(modal(page)).toHaveCount(0);
  });

  test('перетягування мишею переносить картку в інший етап і не відкриває її', async ({ page, request }) => {
    const company = await createCard(request, 'Drag Co');
    await openBoard(page);

    const from = await cardItem(page, company).boundingBox();
    const to = await page.locator('.stage-body').nth(1).boundingBox();
    await page.mouse.move(from!.x + from!.width / 2, from!.y + from!.height / 2);
    await page.mouse.down();
    await page.mouse.move(from!.x + from!.width / 2, from!.y + from!.height / 2 + 20, { steps: 5 });
    await page.mouse.move(to!.x + to!.width / 2, to!.y + 20, { steps: 20 });
    await page.mouse.up();

    await expect.poll(() => stageOf(request, company)).toBe(stageIds[1]);
    await expect(modal(page)).toHaveCount(0);
  });

  test('перетягування з клавіатури переносить картку і не відкриває її', async ({ page, request }) => {
    const company = await createCard(request, 'Key Co');
    // The keyboard does not move a card into an empty column, so the target
    // column gets a card of its own.
    await createCard(request, 'Target Co', 1);
    await openBoard(page);

    await cardItem(page, company).focus();
    await page.keyboard.press('Space');
    await expect(cardItem(page, company)).toHaveClass(/dragging/);
    // Arrow keys are ignored until the lift animation finishes.
    await page.waitForTimeout(300);
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(300);
    await page.keyboard.press('Space');

    await expect.poll(() => stageOf(request, company)).toBe(stageIds[1]);
    await expect(modal(page)).toHaveCount(0);
  });

  // Not a characterization test: before the switch to a native <button> the
  // keyboard could lift a card but not open it.
  test('Enter на картці у фокусі відкриває її', async ({ page, request }) => {
    const company = await createCard(request, 'Enter Co');
    await openBoard(page);

    await cardItem(page, company).focus();
    await page.keyboard.press('Enter');
    await expect(modal(page)).toBeVisible();
  });

  test('наведення на картку не змінює її фон', async ({ page, request }) => {
    const company = await createCard(request, 'Hover Co');
    await openBoard(page);

    await cardItem(page, company).hover();
    await expect(cardItem(page, company)).toHaveCSS('background-color', SURFACE);
  });

  test('форма нової картки ставить фокус у «Компанія», а набір у «Посада» його не забирає', async ({ page }) => {
    await openBoard(page);

    await page.locator('.add-card-button').first().click();
    const company = page.locator('input[placeholder="Компанія"]');
    const position = page.locator('input[placeholder="Посада"]');
    await expect(company).toBeFocused();
    await page.keyboard.type('Focus Co');
    await position.click();
    await page.keyboard.type('QA');
    await expect(position).toBeFocused();
    await expect(position).toHaveValue('QA');

    await page.click('button:has-text("Скасувати")');
    await expect(company).toHaveCount(0);
  });

  test('клік по назві етапу ставить фокус у поле перейменування, Escape лишає назву', async ({ page }) => {
    await openBoard(page);
    const title = page.locator('.stage-header h3').first();
    const name = await title.textContent();

    await title.click();
    await expect(page.locator('.stage-name-input')).toBeFocused();
    await page.keyboard.type(' X');
    await page.keyboard.press('Escape');

    await expect(title).toHaveText(name!);
  });
});
