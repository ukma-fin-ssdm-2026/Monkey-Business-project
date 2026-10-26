/**
 * Інструмент: Claude
 * Застосування: Заміна атрибута autoFocus (SonarQube typescript:S9379) на
 * явне переведення фокуса в поле, яке з'являється після дії користувача.
 * Верифікація: e2e/test_board_interactions.spec.ts до і після зміни: фокус у
 * полі «Компанія» нової картки та в полі перейменування етапу, набір у сусіднє
 * поле фокус не забирає.
 */

// Pass as `ref`. React calls a ref with the element when it mounts; the
// function has to stay the same object between renders, otherwise React calls
// it again on every render and the focus jumps back while typing elsewhere.
export function focusOnMount(element: HTMLElement | null) {
  element?.focus();
}
