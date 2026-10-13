import { useTranslation } from "@frutti/i18n";
import { Input } from "@frutti/ui";

import { BOX_TYPES, type BoxInputs, wholeCount } from "./boxes";

// One input per box type, for the boxes a sale leaves or a pickup takes back. Whole counts, empty means none.
export function BoxCountInputs({ inputs, onChange }: { inputs: BoxInputs; onChange: (next: BoxInputs) => void }) {
  const { t } = useTranslation();
  return (
    <>
      {BOX_TYPES.map((box) => (
        <div key={box} className="flex items-center justify-between gap-3">
          <label htmlFor={`boxes-${box}`} className="font-semibold">
            {box === "small" ? t("truck.boxes.small") : t("truck.boxes.big")}
          </label>
          <Input
            id={`boxes-${box}`}
            inputMode="numeric"
            placeholder="0"
            className="w-28 text-xl"
            value={inputs[box]}
            aria-invalid={wholeCount(inputs[box]) === null}
            onChange={(event) => onChange({ ...inputs, [box]: event.target.value })}
          />
        </div>
      ))}
    </>
  );
}
