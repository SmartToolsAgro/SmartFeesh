import { useTranslation } from "@frutti/i18n";
import { Icon } from "@frutti/ui";
import { Link } from "react-router";

// The way back to "Ma journée" from every driver screen but that one. It sits in the header, where the logo is on
// that screen, so it is in view wherever the screen is scrolled (D-168; it used to sit under the content).
export function BackToDay() {
  const { t } = useTranslation();
  return (
    <Link
      to="/"
      aria-label={t("truck.backToDay")}
      title={t("truck.backToDay")}
      className="grid size-10 flex-none place-items-center rounded-full bg-white/15"
    >
      <Icon name="home" className="size-5" />
    </Link>
  );
}
