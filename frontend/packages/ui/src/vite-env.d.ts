// `?raw` imports (sprite.svg) are resolved by Vite and by Vitest.
declare module "*.svg?raw" {
  const content: string;
  export default content;
}
