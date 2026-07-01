// MV3 service worker (WXT). Ephemeral by design — opens the side panel from the toolbar.
export default defineBackground(() => {
  chrome.runtime.onInstalled.addListener(() => {
    chrome.sidePanel?.setPanelBehavior?.({ openPanelOnActionClick: true }).catch(() => {});
  });
});
