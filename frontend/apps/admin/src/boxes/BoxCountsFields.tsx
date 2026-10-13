import { useTranslation } from "@frutti/i18n";
import { Card, CardTitle, Field, Input } from "@frutti/ui";
import { useId } from "react";

import { BOX_TYPES, type BoxCountInputs } from "./shared";

/** The returnable boxes of a receipt or a load: one count per box type, empty for none (D-122). */
export function BoxCountsFields({
  title,
  hint,
  value,
  onChange,
  errors,
}: {
  title: string;
  hint: string;
  value: BoxCountInputs;
  onChange: (next: BoxCountInputs) => void;
  errors: Record<string, string>;
}) {
  const { t } = useTranslation();
  const formId = useId();
  return (
    <Card className="flex flex-col gap-3" data-testid="box-counts">
      <CardTitle className="mb-0">{title}</CardTitle>
      <p className="text-[0.85rem] text-ink-2">{hint}</p>
      <div className="grid grid-cols-2 gap-4 max-[640px]:grid-cols-1">
        {BOX_TYPES.map((boxType) => {
          const inputId = `${formId}-${boxType}`;
          const error = errors[`boxes.${boxType}`] ?? errors.boxes;
          return (
            <Field key={boxType} label={t(`admin.boxes.types.${boxType}`)} htmlFor={inputId} error={error}>
              <Input
                id={inputId}
                inputMode="numeric"
                autoComplete="off"
                placeholder="0"
                className="num"
                value={value[boxType]}
                onChange={(event) => onChange({ ...value, [boxType]: event.target.value })}
                aria-invalid={error ? true : undefined}
              />
            </Field>
          );
        })}
      </div>
    </Card>
  );
}
