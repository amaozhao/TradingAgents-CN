import type { Page } from "@playwright/test"

export async function installNotificationMocks(page: Page) {
  await page.addInitScript({
    content: `
      (() => {
        const NativeWebSocket = window.WebSocket;

        function E2EMockWebSocket(url) {
          if (!String(url).includes("/api/ws/notifications")) {
            return new NativeWebSocket(url);
          }

          this.url = url;
          this.readyState = E2EMockWebSocket.CONNECTING;
          this.onopen = null;
          this.onclose = null;
          this.onerror = null;
          this.onmessage = null;
          this.listeners = {};

          window.setTimeout(() => {
            this.readyState = E2EMockWebSocket.OPEN;
            const event = new Event("open");
            if (this.onopen) this.onopen(event);
            (this.listeners.open || []).forEach((listener) => listener(event));
          }, 0);
        }

        E2EMockWebSocket.CONNECTING = 0;
        E2EMockWebSocket.OPEN = 1;
        E2EMockWebSocket.CLOSING = 2;
        E2EMockWebSocket.CLOSED = 3;
        E2EMockWebSocket.prototype.close = function close() {
          this.readyState = E2EMockWebSocket.CLOSED;
          const event = new Event("close");
          if (this.onclose) this.onclose(event);
          (this.listeners.close || []).forEach((listener) => listener(event));
        };
        E2EMockWebSocket.prototype.send = function send() {};
        E2EMockWebSocket.prototype.addEventListener = function addEventListener(type, listener) {
          this.listeners[type] = this.listeners[type] || [];
          this.listeners[type].push(listener);
        };
        E2EMockWebSocket.prototype.removeEventListener = function removeEventListener(type, listener) {
          this.listeners[type] = (this.listeners[type] || []).filter((item) => item !== listener);
        };

        Object.defineProperty(window, "WebSocket", {
          configurable: true,
          writable: true,
          value: E2EMockWebSocket
        });
      })();
    `
  })

  await page.route("**/api/notifications/unread_count", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, data: { count: 0 } })
    })
  })

  await page.route("**/api/notifications**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, data: { items: [], total: 0 } })
    })
  })
}
