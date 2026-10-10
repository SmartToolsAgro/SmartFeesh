import path from "node:path";

/** The owner's saved session, written by owner.setup.ts (login `owner` from `manage.py seed_dev`). */
export const OWNER_STATE = path.join(import.meta.dirname, "..", ".auth", "owner.json");
