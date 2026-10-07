import { expect, type Locator, type Page } from "@playwright/test";

type Scope = Page | Locator;

/**
 * shadcn Select（基于 base-ui）渲染的是 button[role=combobox] + div[role=option]，
 * 没有原生 <select>，因此不能用 Playwright 的 selectOption()。
 * 这里统一封装为「点开触发按钮 → 点选项文本」。
 *
 * @param page   页面（选项弹层挂在 body 上，始终用 page 查找）
 * @param name   触发按钮的 aria-label
 * @param optionLabel 选项可见文本
 * @param scope  触发按钮所在范围（例如 dialog），默认整个页面
 */
export async function chooseSelect(
  page: Page,
  name: string,
  optionLabel: string,
  scope?: Scope,
) {
  const trigger = (scope ?? page).getByRole("combobox", { name, exact: true });
  await expect(trigger).toBeVisible();
  await trigger.click();
  await page.getByRole("option", { name: optionLabel, exact: true }).click();
}

/** 条件选股市场的 value → 选项文本 */
export const MARKET_OPTION_LABELS = {
  CN: "A股 · CNY",
  HK: "港股 · HKD",
  US: "美股 · USD",
} as const;
