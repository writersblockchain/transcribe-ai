import { test, expect } from '@playwright/test';
const stories = ['signed-out','sign-in-error','missing-api-key','empty-library','saved-conversations','transcript','no-search-results','unsaved-changes','processing','download-error'];
for (const width of [390,1280]) {
  for (const story of stories) {
    test(`${story} at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      const errors=[];
      page.on('pageerror',error=>errors.push(error.message));
      await page.goto(`/iframe.html?id=cadence-screens--${story}&viewMode=story`);
      const frame = page.frameLocator('iframe[title^="Cadence visual fixture"]');
      await expect(frame.locator('h1')).toContainText('Every voice.');
      await expect.poll(async()=>page.locator('iframe[title^="Cadence visual fixture"]').evaluate(el=>!!el.contentWindow.__visualReady)).toBe(true);
      if (story === 'transcript') await expect(frame.locator('.utterance')).toHaveCount(4);
      if (story === 'no-search-results') await expect(frame.locator('#utterances')).toContainText('No matching passages.');
      if (story === 'empty-library') await expect(frame.locator('#library-status')).toContainText('Your next conversation');
      if (story === 'processing') await expect(frame.locator('#submit')).toBeDisabled();
      if (story === 'download-error') await expect(frame.locator('#status')).toHaveClass('error');
      if (story === 'unsaved-changes') await expect(frame.locator('#save-status')).toContainText('Unsaved changes');
      expect(await frame.locator('body').evaluate(el=>el.scrollWidth<=window.innerWidth)).toBe(true);
      expect(errors).toEqual([]);
    });
  }
}
