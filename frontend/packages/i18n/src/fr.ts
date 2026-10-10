/** French texts: the reference language. Every key must exist here; other languages fall back to it. */
export const fr = {
  common: {
    currency: "DT",
    loading: "Chargement…",
    logout: "Se déconnecter",
    comingSoon: "Bientôt disponible",
    comingSoonBody: "Cet écran sera construit dans une prochaine étape du projet.",
    serverUnreachable: "Serveur injoignable. Vérifiez le réseau puis rechargez la page.",
  },
  brand: {
    tagline: "Gestion & distribution",
  },
  theme: {
    label: "Thème d'affichage",
    light: "Thème clair",
    system: "Thème de l'appareil",
    dark: "Thème sombre",
  },
  auth: {
    title: "Connexion",
    username: "Identifiant",
    password: "Mot de passe",
    submit: "Se connecter",
    submitting: "Connexion…",
    tooManyAttempts: "Trop de tentatives. Réessayez dans une minute.",
    networkError: "Connexion impossible. Vérifiez le réseau puis réessayez.",
  },
  roles: {
    owner: "Propriétaire",
    manager: "Gestionnaire",
    accountant: "Comptable",
    driver: "Chauffeur",
  },
  admin: {
    appName: "Administration",
    modules: "Modules",
    wrongApp: "Ce compte est un compte chauffeur. Utilisez l'application chauffeur.",
    groups: {
      steering: "Pilotage",
      sales: "Commercial",
      goods: "Marchandise",
      finance: "Finances",
    },
    nav: {
      dashboard: "Tableau de bord",
      quotes: "Devis",
      sales: "Ventes & factures",
      customers: "Clients",
      stock: "Stock frigo & camions",
      purchases: "Achats",
      suppliers: "Fournisseurs",
      expenses: "Charges",
      payroll: "Personnel & salaires",
      profitSharing: "Partage des bénéfices",
      closing: "Clôture mensuelle",
    },
    dashboard: {
      hello: "Bonjour {{name}}",
      body: "Le socle est en place. Les indicateurs du jour apparaîtront ici dès que le stock et les ventes seront enregistrés dans l'application.",
    },
  },
  truck: {
    appName: "Chauffeur",
    navigation: "Navigation camion",
    wrongApp: "Ce compte n'est pas un compte chauffeur. Utilisez l'application d'administration.",
    hello: "Bonjour {{name}}",
    tabs: {
      day: "Ma journée",
      stock: "Mon stock",
      sale: "Vente",
      closing: "Clôture",
    },
  },
};

/** Shape of a full translation: same keys as French, any text. */
export type Translation = typeof fr;

type DeepPartial<T> = { [K in keyof T]?: T[K] extends object ? DeepPartial<T[K]> : T[K] };
/** Other languages may be incomplete: a missing key shows the French text. */
export type PartialTranslation = DeepPartial<Translation>;
