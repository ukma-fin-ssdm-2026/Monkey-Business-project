# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: e2e/test_board_interactions.spec.ts >> Lab08: поведінка дошки до і після рефакторингу >> перетягування мишею переносить картку в інший етап і не відкриває її
- Location: e2e/test_board_interactions.spec.ts:119:3

# Error details

```
TypeError: Cannot read properties of undefined (reading 'stage_id')
```

# Page snapshot

```yaml
- generic [ref=e3]:
  - banner [ref=e4]:
    - generic [ref=e5]:
      - heading "Tech Interview Board" [level=1] [ref=e6]
      - generic [ref=e7]: "board_id: 881c9ea7-0d0c-4864-bafe-fbcb2bf70722"
    - generic [ref=e8]:
      - generic [ref=e9]: e2e@example.com (candidate)
      - button "Ментори" [ref=e10] [cursor=pointer]
      - button "Змінити дошку" [ref=e11] [cursor=pointer]
      - button "Вийти" [ref=e12] [cursor=pointer]
  - generic [ref=e13]:
    - generic [ref=e14]:
      - generic [ref=e15]:
        - heading "Відгук" [level=3] [ref=e16] [cursor=pointer]
        - generic [ref=e17]: "0"
        - button "✕" [ref=e18] [cursor=pointer]
      - button "+ Картка" [ref=e20] [cursor=pointer]
    - generic [ref=e21]:
      - generic [ref=e22]:
        - heading "Скринінг" [level=3] [ref=e23] [cursor=pointer]
        - generic [ref=e24]: "1"
        - button "✕" [ref=e25] [cursor=pointer]
      - button "Drag Co 1793390493753 Активна Engineer" [ref=e27] [cursor=pointer]:
        - generic [ref=e28]:
          - generic [ref=e29]: Drag Co 1793390493753
          - generic [ref=e30]: Активна
        - generic [ref=e31]: Engineer
      - button "+ Картка" [ref=e32] [cursor=pointer]
    - generic [ref=e33]:
      - generic [ref=e34]:
        - heading "Технічне інтерв'ю" [level=3] [ref=e35] [cursor=pointer]
        - generic [ref=e36]: "0"
        - button "✕" [ref=e37] [cursor=pointer]
      - button "+ Картка" [ref=e39] [cursor=pointer]
    - generic [ref=e40]:
      - generic [ref=e41]:
        - heading "Офер" [level=3] [ref=e42] [cursor=pointer]
        - generic [ref=e43]: "0"
        - button "✕" [ref=e44] [cursor=pointer]
      - button "+ Картка" [ref=e46] [cursor=pointer]
    - button "+ Етап" [ref=e47] [cursor=pointer]
```

# Test source

```ts
  1   | /**
  2   |  * Інструмент: Claude
  3   |  * Застосування: Характеризаційні e2e-тести Lab08 – фіксують поточну поведінку
  4   |  * компонентів дошки (CardItem, CardModal, MentorsPanel, NewCardForm,
  5   |  * StageColumn) перед рефакторингом зауважень SonarQube S6848 і S9379.
  6   |  * Верифікація: Прогін у Chrome проти API з PostgreSQL на гілці pre-refactor
  7   |  * і після кожного кроку рефакторингу.
  8   |  *
  9   |  * Як і test_performance.spec.ts, потребує запущених API, Vite dev-сервера та
  10  |  * користувача з дошкою; адреси й обліковий запис змінюються через змінні E2E_*.
  11  |  * Тести створюють власні картки і видаляють лише їх.
  12  |  */
  13  | 
  14  | import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
  15  | 
  16  | const API_URL = process.env.E2E_API_URL ?? 'http://localhost:3000';
  17  | const UI_URL = process.env.E2E_UI_URL ?? 'http://localhost:5173';
  18  | const EMAIL = process.env.E2E_EMAIL ?? 'e2e@example.com';
  19  | const PASSWORD = process.env.E2E_PASSWORD ?? '12345678';
  20  | const BOARD_ID = process.env.E2E_BOARD_ID ?? '881c9ea7-0d0c-4864-bafe-fbcb2bf70722';
  21  | const SURFACE = 'rgb(255, 255, 255)';
  22  | 
  23  | let headers: Record<string, string>;
  24  | let stageIds: string[];
  25  | let createdCardIds: string[];
  26  | 
  27  | async function createCard(request: APIRequestContext, name: string, stage = 0): Promise<string> {
  28  |   const company = `${name} ${Date.now()}`;
  29  |   const response = await request.post(`${API_URL}/v1/boards/${BOARD_ID}/cards`, {
  30  |     data: { stage_id: stageIds[stage], company, position: 'Engineer' },
  31  |     headers,
  32  |   });
  33  |   expect(response.status()).toBe(201);
  34  |   createdCardIds.push((await response.json()).id);
  35  |   return company;
  36  | }
  37  | 
  38  | async function stageOf(request: APIRequestContext, company: string): Promise<string> {
  39  |   const cards = await (
  40  |     await request.get(`${API_URL}/v1/boards/${BOARD_ID}/cards`, { headers })
  41  |   ).json();
> 42  |   return cards.items.find((card: { company: string }) => card.company === company).stage_id;
      |                                                                                   ^ TypeError: Cannot read properties of undefined (reading 'stage_id')
  43  | }
  44  | 
  45  | async function openBoard(page: Page) {
  46  |   await page.goto(UI_URL);
  47  |   await page.fill('input[type="email"]', EMAIL);
  48  |   await page.fill('input[type="password"]', PASSWORD);
  49  |   await page.click('button:has-text("Увійти")');
  50  |   await page.fill('input[placeholder="3fa85f64-5717-4562-b3fc-2c963f66afa6"]', BOARD_ID);
  51  |   await page.click('button:has-text("Відкрити дошку")');
  52  |   await page.locator('.stage-column').first().waitFor();
  53  | }
  54  | 
  55  | const cardItem = (page: Page, company: string) => page.locator('.card-item', { hasText: company });
  56  | const modal = (page: Page) => page.locator('.modal-card');
  57  | 
  58  | test.describe('Lab08: поведінка дошки до і після рефакторингу', () => {
  59  |   test.beforeEach(async ({ request }) => {
  60  |     const login = await request.post(`${API_URL}/v1/auth/login`, {
  61  |       data: { email: EMAIL, password: PASSWORD },
  62  |     });
  63  |     headers = { Authorization: `Bearer ${(await login.json()).access_token}` };
  64  |     const stages = await (
  65  |       await request.get(`${API_URL}/v1/boards/${BOARD_ID}/stages`, { headers })
  66  |     ).json();
  67  |     stageIds = stages.map((stage: { id: string }) => stage.id);
  68  |     createdCardIds = [];
  69  |   });
  70  | 
  71  |   test.afterEach(async ({ request }) => {
  72  |     for (const id of createdCardIds) {
  73  |       await request.delete(`${API_URL}/v1/boards/${BOARD_ID}/cards/${id}`, { headers });
  74  |     }
  75  |   });
  76  | 
  77  |   test('картка відкривається кліком; модалку закриває фон і ✕, але не клік усередині', async ({ page, request }) => {
  78  |     const company = await createCard(request, 'Modal Co');
  79  |     await openBoard(page);
  80  | 
  81  |     await cardItem(page, company).click();
  82  |     await expect(modal(page)).toBeVisible();
  83  |     await modal(page).locator('h2').click();
  84  |     await expect(modal(page)).toBeVisible();
  85  |     await page.mouse.click(10, 10);
  86  |     await expect(modal(page)).toHaveCount(0);
  87  | 
  88  |     await cardItem(page, company).click();
  89  |     await modal(page).locator('.modal-header button').click();
  90  |     await expect(modal(page)).toHaveCount(0);
  91  |   });
  92  | 
  93  |   test('клік по фону закриває модалку і після прокручування', async ({ page, request }) => {
  94  |     const company = await createCard(request, 'Scroll Co');
  95  |     await page.setViewportSize({ width: 1280, height: 400 });
  96  |     await openBoard(page);
  97  | 
  98  |     await cardItem(page, company).click();
  99  |     const overlay = page.locator('.modal-overlay');
  100 |     const scrolled = await overlay.evaluate((el) => {
  101 |       el.scrollTo(0, el.scrollHeight);
  102 |       return el.scrollTop;
  103 |     });
  104 |     expect(scrolled).toBeGreaterThan(0);
  105 |     await page.mouse.click(10, 390);
  106 |     await expect(modal(page)).toHaveCount(0);
  107 |   });
  108 | 
  109 |   test('панель менторів закриває клік по фону, але не клік усередині', async ({ page }) => {
  110 |     await openBoard(page);
  111 | 
  112 |     await page.click('button:has-text("Ментори")');
  113 |     await modal(page).locator('h2').click();
  114 |     await expect(modal(page)).toBeVisible();
  115 |     await page.mouse.click(10, 10);
  116 |     await expect(modal(page)).toHaveCount(0);
  117 |   });
  118 | 
  119 |   test('перетягування мишею переносить картку в інший етап і не відкриває її', async ({ page, request }) => {
  120 |     const company = await createCard(request, 'Drag Co');
  121 |     await openBoard(page);
  122 | 
  123 |     const from = await cardItem(page, company).boundingBox();
  124 |     const to = await page.locator('.stage-body').nth(1).boundingBox();
  125 |     await page.mouse.move(from!.x + from!.width / 2, from!.y + from!.height / 2);
  126 |     await page.mouse.down();
  127 |     await page.mouse.move(from!.x + from!.width / 2, from!.y + from!.height / 2 + 20, { steps: 5 });
  128 |     await page.mouse.move(to!.x + to!.width / 2, to!.y + 20, { steps: 20 });
  129 |     await page.mouse.up();
  130 | 
  131 |     await expect.poll(() => stageOf(request, company)).toBe(stageIds[1]);
  132 |     await expect(modal(page)).toHaveCount(0);
  133 |   });
  134 | 
  135 |   test('перетягування з клавіатури переносить картку і не відкриває її', async ({ page, request }) => {
  136 |     const company = await createCard(request, 'Key Co');
  137 |     // The keyboard does not move a card into an empty column, so the target
  138 |     // column gets a card of its own.
  139 |     await createCard(request, 'Target Co', 1);
  140 |     await openBoard(page);
  141 | 
  142 |     await cardItem(page, company).focus();
```