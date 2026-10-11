import { Field, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@frutti/ui";

/** A labelled drop-down of `{ value, label }` options (the Select of the design system, as one field). */
export function CostSelect({
  id,
  label,
  value,
  onChange,
  options,
  placeholder,
  error,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder: string;
  error?: string;
}) {
  return (
    <Field label={label} htmlFor={id} error={error}>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id={id} aria-invalid={error ? true : undefined}>
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
  );
}
