import type { Session } from "@frutti/auth";
import {
  createMember,
  deactivateMember,
  getListMembersQueryKey,
  type Member,
  type RoleEnum,
  reactivateMember,
  resetMemberPassword,
  setMemberRole,
  useListMembers,
} from "@frutti/api";
import { useTranslation } from "@frutti/i18n";
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
  Field,
  Icon,
  Input,
  PageHeader,
  Pill,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Table,
  Td,
  Th,
  toast,
} from "@frutti/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { useOutletContext } from "react-router";

import { fieldErrors } from "../lib/errors";

const ROLES: RoleEnum[] = ["owner", "manager", "accountant", "driver"];

function errorText(failure: unknown, fallback: string): string {
  return Object.values(fieldErrors(failure))[0] ?? fallback;
}

function AddMemberDialog({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const formId = useId();
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [role, setRole] = useState<RoleEnum>("manager");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  const create = useMutation({
    mutationFn: () =>
      createMember({
        username: username.trim(),
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        role,
        password,
      }),
    onSuccess: async () => {
      toast.success(t("admin.users.created"));
      await queryClient.invalidateQueries({ queryKey: getListMembersQueryKey() });
      onDone();
    },
    onError: (failure) => {
      const found = fieldErrors(failure);
      if (Object.keys(found).length > 0) setErrors(found);
      else toast.error(t("admin.users.error"));
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setErrors({});
    create.mutate();
  };

  return (
    <DialogContent className="w-[min(480px,calc(100vw-2rem))]">
      <DialogTitle>{t("admin.users.createTitle")}</DialogTitle>
      <DialogDescription>{t("admin.users.createDescription")}</DialogDescription>
      <form onSubmit={submit} className="flex flex-col gap-3.5">
        <Field label={t("admin.users.username")} htmlFor={`${formId}-username`} error={errors.username}>
          <Input
            id={`${formId}-username`}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="off"
          />
        </Field>
        <div className="grid grid-cols-2 gap-3 max-[520px]:grid-cols-1">
          <Field label={t("admin.users.firstName")} htmlFor={`${formId}-first`} error={errors.first_name}>
            <Input id={`${formId}-first`} value={firstName} onChange={(event) => setFirstName(event.target.value)} />
          </Field>
          <Field label={t("admin.users.lastName")} htmlFor={`${formId}-last`} error={errors.last_name}>
            <Input id={`${formId}-last`} value={lastName} onChange={(event) => setLastName(event.target.value)} />
          </Field>
        </div>
        <Field label={t("admin.users.role")} htmlFor={`${formId}-role`} error={errors.role}>
          <Select value={role} onValueChange={(value) => setRole(value as RoleEnum)}>
            <SelectTrigger id={`${formId}-role`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ROLES.map((value) => (
                <SelectItem key={value} value={value}>
                  {t(`roles.${value}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label={t("admin.users.password")} htmlFor={`${formId}-password`} error={errors.password}>
          <Input
            id={`${formId}-password`}
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
          />
        </Field>
        <DialogFooter>
          <Button variant="ghost" onClick={onDone}>
            {t("admin.users.cancel")}
          </Button>
          <Button type="submit" variant="primary" disabled={create.isPending}>
            {t("admin.users.create")}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
}

function ResetPasswordDialog({ member, onDone }: { member: Member; onDone: () => void }) {
  const { t } = useTranslation();
  const formId = useId();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | undefined>();
  const name = member.user.first_name || member.user.username;

  const reset = useMutation({
    mutationFn: () => resetMemberPassword(member.id, { new_password: password }),
    onSuccess: () => {
      toast.success(t("admin.users.passwordReset"));
      onDone();
    },
    onError: (failure) => setError(errorText(failure, t("admin.users.error"))),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setError(undefined);
    reset.mutate();
  };

  return (
    <DialogContent className="w-[min(440px,calc(100vw-2rem))]">
      <DialogTitle>{t("admin.users.resetTitle", { name })}</DialogTitle>
      <DialogDescription>{t("admin.users.resetDescription")}</DialogDescription>
      <form onSubmit={submit} className="flex flex-col gap-3.5">
        <Field label={t("admin.users.password")} htmlFor={`${formId}-password`} error={error}>
          <Input
            id={`${formId}-password`}
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
          />
        </Field>
        <DialogFooter>
          <Button variant="ghost" onClick={onDone}>
            {t("admin.users.cancel")}
          </Button>
          <Button type="submit" variant="primary" disabled={reset.isPending}>
            {t("admin.users.resetPassword")}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
}

function MemberRow({ member, isMe }: { member: Member; isMe: boolean }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [resetting, setResetting] = useState(false);
  const refresh = () => queryClient.invalidateQueries({ queryKey: getListMembersQueryKey() });

  const changeRole = useMutation({
    mutationFn: (next: RoleEnum) => setMemberRole(member.id, { role: next }),
    onSuccess: async () => {
      toast.success(t("admin.users.roleChanged"));
      await refresh();
    },
    onError: (failure) => toast.error(errorText(failure, t("admin.users.error"))),
  });

  const toggleActive = useMutation({
    mutationFn: () => (member.is_active ? deactivateMember(member.id) : reactivateMember(member.id)),
    onSuccess: async () => {
      toast.success(t(member.is_active ? "admin.users.deactivated" : "admin.users.reactivated"));
      await refresh();
    },
    onError: (failure) => toast.error(errorText(failure, t("admin.users.error"))),
  });

  const fullName = `${member.user.first_name} ${member.user.last_name}`.trim() || member.user.username;

  return (
    <tr>
      <Td>
        <div className="flex items-center gap-2.5">
          {member.user.avatar_url ? (
            <img src={member.user.avatar_url} alt="" className="size-[30px] flex-none rounded-full object-cover" />
          ) : (
            <div className="grid size-[30px] flex-none place-items-center rounded-full bg-sea-soft text-[0.75rem] font-bold text-sea">
              {fullName.charAt(0).toUpperCase()}
            </div>
          )}
          <div className="leading-tight">
            <div className="font-semibold">
              {fullName}
              {isMe && <span className="ms-2 text-[0.75rem] text-ink-2">({t("admin.users.you")})</span>}
            </div>
            <div className="text-[0.8rem] text-ink-2">{member.user.username}</div>
          </div>
        </div>
      </Td>
      <Td>
        <Select
          value={member.role}
          onValueChange={(value) => changeRole.mutate(value as RoleEnum)}
          disabled={isMe || changeRole.isPending}
        >
          <SelectTrigger aria-label={t("admin.users.role")} className="min-w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ROLES.map((value) => (
              <SelectItem key={value} value={value}>
                {t(`roles.${value}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Td>
      <Td>
        {member.is_active ? (
          <Pill tone="good">{t("admin.users.active")}</Pill>
        ) : (
          <Pill tone="neutral">{t("admin.users.inactive")}</Pill>
        )}
      </Td>
      <Td>
        <div className="flex flex-wrap justify-end gap-1.5">
          <Button variant="ghost" onClick={() => setResetting(true)}>
            <Icon name="lock" />
            {t("admin.users.resetPassword")}
          </Button>
          {!isMe && (
            <Button variant="ghost" disabled={toggleActive.isPending} onClick={() => toggleActive.mutate()}>
              {member.is_active ? t("admin.users.deactivate") : t("admin.users.reactivate")}
            </Button>
          )}
        </div>
        <Dialog open={resetting} onOpenChange={(open) => !open && setResetting(false)}>
          {resetting && <ResetPasswordDialog member={member} onDone={() => setResetting(false)} />}
        </Dialog>
      </Td>
    </tr>
  );
}

/** "Utilisateurs" in Paramètres: who logs in, with which role. Owner only; the server checks it too (D-123). */
export function UsersPage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const query = useListMembers();
  const [adding, setAdding] = useState(false);

  return (
    <>
      <PageHeader eyebrow={t("admin.settings.title")} title={t("admin.users.title")}>
        <Button variant="primary" onClick={() => setAdding(true)}>
          <Icon name="plus" />
          {t("admin.users.add")}
        </Button>
      </PageHeader>
      {query.isPending ? (
        <p className="text-ink-2">{t("common.loading")}</p>
      ) : query.data ? (
        query.data.length === 0 ? (
          <p className="text-ink-2">{t("admin.users.empty")}</p>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>{t("admin.users.columns.user")}</Th>
                <Th>{t("admin.users.columns.role")}</Th>
                <Th>{t("admin.users.columns.status")}</Th>
                <Th>{t("admin.users.columns.actions")}</Th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((member) => (
                <MemberRow key={member.id} member={member} isMe={member.user.id === session.user.id} />
              ))}
            </tbody>
          </Table>
        )
      ) : (
        <p role="alert" className="text-bad">
          {t("common.serverUnreachable")}
        </p>
      )}
      <Dialog open={adding} onOpenChange={(open) => !open && setAdding(false)}>
        {adding && <AddMemberDialog onDone={() => setAdding(false)} />}
      </Dialog>
    </>
  );
}
