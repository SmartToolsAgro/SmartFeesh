import { ApiStatus, BRAND } from "@frutti/ui";

// Scaffold screen. The real shell (layout, navigation, login) comes in P0-T06 and P0-T07.
export function App() {
  return (
    <main>
      <h1>{BRAND.name}</h1>
      <p>Espace administration</p>
      <ApiStatus />
    </main>
  );
}
