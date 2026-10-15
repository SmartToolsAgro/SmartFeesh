import { ApiError, type CustomerChoice, useCreateMyCustomer } from "@frutti/api";
import { useTranslation } from "@frutti/i18n";
import { Button, Card, Field, Input } from "@frutti/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { messagesOf } from "./messages";

/** A driver adds a customer they sell to: a name, and a phone and a city when known. Needs the network (P3-T03, D-152). */
export function NewCustomerForm({
  onAdded,
  onCancel,
}: {
  onAdded: (customer: CustomerChoice) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [city, setCity] = useState("");
  const [error, setError] = useState("");
  const create = useCreateMyCustomer({
    mutation: {
      onSuccess: (customer) => {
        void queryClient.invalidateQueries();
        onAdded(customer);
      },
      onError: (failure) =>
        setError(failure instanceof ApiError ? messagesOf(failure.body).join(" ") : t("truck.newCustomer.failed")),
    },
  });

  return (
    <Card className="space-y-3">
      <h2>{t("truck.newCustomer.title")}</h2>
      <Field label={t("truck.newCustomer.name")} htmlFor="new-customer-name">
        <Input
          id="new-customer-name"
          className="text-lg"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </Field>
      <Field label={t("truck.newCustomer.phone")} htmlFor="new-customer-phone">
        <Input
          id="new-customer-phone"
          inputMode="tel"
          className="text-lg"
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
        />
      </Field>
      <Field label={t("truck.newCustomer.city")} htmlFor="new-customer-city">
        <Input
          id="new-customer-city"
          className="text-lg"
          value={city}
          onChange={(event) => setCity(event.target.value)}
        />
      </Field>
      {error === "" ? null : <p className="text-bad">{error}</p>}
      <Button
        size="lg"
        variant="primary"
        className="py-4 text-lg"
        disabled={name.trim() === "" || create.isPending}
        onClick={() => {
          setError("");
          create.mutate({ data: { name: name.trim(), phone: phone.trim(), city: city.trim() } });
        }}
      >
        {t("truck.newCustomer.save")}
      </Button>
      <Button size="lg" className="py-4 text-lg" onClick={onCancel}>
        {t("truck.newCustomer.cancel")}
      </Button>
    </Card>
  );
}
