import { useTranslation } from "@frutti/i18n";
import { Button } from "@frutti/ui";
import { Link } from "react-router";

// The way back to "Ma journée" from every driver screen but that one, under the screen's content (and under a
// screen that crashed, see ScreenError). Same button as the one the boxes pickup used.
export function BackToDay({ pathname }: { pathname: string }) {
  const { t } = useTranslation();
  if (pathname === "/") return null;
  return (
    <Button asChild size="lg" className="py-4 text-lg">
      <Link to="/">{t("truck.backToDay")}</Link>
    </Button>
  );
}
