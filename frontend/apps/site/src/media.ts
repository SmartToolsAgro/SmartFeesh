// The pictures of the site, made for it with Artlist (D-186): a dawn shot of the port (still and 10-second loop)
// and a flat-lay of the catch, cut into one tile per kind of product. A product's own photo, uploaded in the
// office app, always comes first.

export const HERO = {
  poster: "/media/port-dawn.webp",
  webm: "/media/port-dawn.webm",
  mp4: "/media/port-dawn.mp4",
};
export const CATCH = "/media/catch-flatlay.webp";

const TILE = {
  dorade: "/media/p-dorade.webp",
  loup: "/media/p-loup.webp",
  rouget: "/media/p-rouget.webp",
  crevette: "/media/p-crevette.webp",
  poulpe: "/media/p-poulpe.webp",
  coquillage: "/media/p-coquillage.webp",
};

// Words of a product's name, without accents, and the tile they call for. First match wins.
const BY_NAME: [RegExp, string][] = [
  [/rouget|pageot|sar\b|rascasse/, TILE.rouget],
  [/loup|bar\b|merou|denti/, TILE.loup],
  [/dorade|daurade|pagre|sole|maquereau|sardine/, TILE.dorade],
  [/crevette|gambas|langoust|cigale|crabe/, TILE.crevette],
  [/poulpe|calamar|seiche|encornet/, TILE.poulpe],
  [/palourde|moule|huitre|coquill|clovisse|praire/, TILE.coquillage],
];

const BY_ILLUSTRATION: Record<string, string> = {
  shrimp: TILE.crevette,
  peeled: TILE.crevette,
  fish: TILE.dorade,
  bass: TILE.loup,
  squid: TILE.poulpe,
  octopus: TILE.poulpe,
  mussel: TILE.coquillage,
  mix: CATCH,
};

function plain(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

export function pictureOf(product: { name: string; illustration: string; photo_url: string | null }): string {
  if (product.photo_url) return product.photo_url;
  const name = plain(product.name);
  const named = BY_NAME.find(([words]) => words.test(name));
  return named?.[1] ?? BY_ILLUSTRATION[product.illustration] ?? CATCH;
}
