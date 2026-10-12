import { type ImportReport, runImport } from "@frutti/api";
import type { Session } from "@frutti/auth";
import { useTranslation } from "@frutti/i18n";
import { Button, Card, CardTitle, EmptyState, Icon, PageHeader, Pill, Table, Td, Th, toast } from "@frutti/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useOutletContext } from "react-router";

import { fieldErrors } from "../lib/errors";

const KINDS = ["products", "suppliers", "customers", "employees", "opening_stock"] as const;
type Kind = (typeof KINDS)[number];

const ROW_TONES = { created: "good", skipped: "neutral", error: "bad" } as const;

/** "Import de données": fill an Excel template, check it (nothing is written), then import it (P4-T01, D-112). */
export function ImportPage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const queryClient = useQueryClient();
  const fileId = useId();
  const [kind, setKind] = useState<Kind>("products");
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);

  const reset = (next: { kind?: Kind; file?: File | null }) => {
    if (next.kind) setKind(next.kind);
    if ("file" in next) setFile(next.file ?? null);
    setReport(null);
  };

  const send = useMutation({
    mutationFn: (dryRun: boolean) => {
      if (!file) return Promise.reject(new Error("no file"));
      return runImport(kind, { file, dry_run: dryRun });
    },
    onSuccess: async (result) => {
      setReport(result);
      if (result.committed) {
        toast.success(t("admin.imports.done", { count: result.created }));
        await queryClient.invalidateQueries();
      }
    },
    onError: (failure) => {
      toast.error(Object.values(fieldErrors(failure))[0] ?? t("admin.imports.failed"));
    },
  });

  if (session.role !== "owner") {
    return (
      <>
        <PageHeader eyebrow={t("admin.groups.finance")} title={t("admin.imports.title")} />
        <EmptyState illustration="mix" title={t("admin.imports.ownerOnly")} />
      </>
    );
  }

  // The import is offered only for a file that was just checked without any error.
  const canImport = report !== null && report.dry_run && report.error_count === 0 && report.created > 0;

  return (
    <>
      <PageHeader eyebrow={t("admin.groups.finance")} title={t("admin.imports.title")} />
      <p className="max-w-3xl text-ink-2">{t("admin.imports.intro")}</p>

      <Card className="flex flex-col gap-4">
        <div
          role="group"
          aria-label={t("admin.imports.kind")}
          className="flex flex-wrap gap-1 rounded-control bg-surface-2 p-1"
        >
          {KINDS.map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={kind === value}
              onClick={() => reset({ kind: value, file: null })}
              className={`rounded-[7px] px-3 py-1.5 text-[0.9rem] font-semibold ${kind === value ? "bg-surface text-ink shadow-card" : "text-ink-2"}`}
            >
              {t(`admin.imports.kinds.${value}`)}
            </button>
          ))}
        </div>

        <CardTitle>{t("admin.imports.step1")}</CardTitle>
        <p>
          <a
            href={`/api/v1/imports/${kind}/template`}
            className="font-semibold text-sea hover:underline"
            download={`modele-${kind}.xlsx`}
          >
            {t("admin.imports.download", { name: t(`admin.imports.kinds.${kind}`) })}
          </a>
        </p>

        <CardTitle>{t("admin.imports.step2")}</CardTitle>
        <div className="flex flex-wrap items-center gap-3">
          <label htmlFor={fileId} className="sr-only">
            {t("admin.imports.file")}
          </label>
          <input
            id={fileId}
            key={kind}
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={(event) => reset({ file: event.target.files?.[0] ?? null })}
          />
          <Button disabled={!file || send.isPending} onClick={() => send.mutate(true)}>
            <Icon name="calcheck" />
            {send.isPending ? t("admin.imports.checking") : t("admin.imports.check")}
          </Button>
        </div>

        {report && (
          <div className="flex flex-col gap-3" aria-live="polite">
            <CardTitle>{t("admin.imports.step3")}</CardTitle>
            <p role="status" className="flex flex-wrap items-center gap-2">
              <Pill tone="good">{t("admin.imports.created", { count: report.created })}</Pill>
              <Pill tone="neutral">{t("admin.imports.skipped", { count: report.skipped })}</Pill>
              <Pill tone={report.error_count > 0 ? "bad" : "neutral"}>
                {t("admin.imports.errors", { count: report.error_count })}
              </Pill>
            </p>
            {report.committed ? (
              <p className="font-semibold text-good">{t("admin.imports.done", { count: report.created })}</p>
            ) : report.error_count > 0 ? (
              <p role="alert" className="text-bad">
                {t("admin.imports.fixFirst")}
              </p>
            ) : (
              <p className="text-ink-2">{t("admin.imports.dryRunNote")}</p>
            )}
            <Table>
              <thead>
                <tr>
                  <Th>{t("admin.imports.columns.row")}</Th>
                  <Th>{t("admin.imports.columns.reference")}</Th>
                  <Th>{t("admin.imports.columns.name")}</Th>
                  <Th>{t("admin.imports.columns.result")}</Th>
                </tr>
              </thead>
              <tbody>
                {report.rows.map((row) => (
                  <tr key={row.row}>
                    <Td className="num">{row.row}</Td>
                    <Td className="num">{row.reference}</Td>
                    <Td>{row.name}</Td>
                    <Td>
                      <Pill tone={ROW_TONES[row.status]}>{t(`admin.imports.statuses.${row.status}`)}</Pill>
                      {row.errors.map((error) => (
                        <div key={`${error.column}${error.message}`} className="text-[0.85rem] text-bad">
                          <span className="font-semibold">{error.column}</span> : {error.message}
                        </div>
                      ))}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <div>
              <Button variant="primary" disabled={!canImport || send.isPending} onClick={() => send.mutate(false)}>
                <Icon name="check" />
                {t("admin.imports.confirm", { count: report.created })}
              </Button>
            </div>
          </div>
        )}
      </Card>
    </>
  );
}
