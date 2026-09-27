declare module "*scrollcraft.js";
interface Window {
  ScrollCraft: { mount: (root: HTMLElement) => { layout: () => void } };
}
