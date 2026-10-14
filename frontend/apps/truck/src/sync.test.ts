import { ApiError, createSale, reportSyncProblem } from "@frutti/api";
import type { QueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { listQueue, markRefused, markReported, type QueuedSale, removeQueued } from "./queue";
import { getSyncProblem, sendWaiting, SEND_TIMEOUT_MS } from "./sync";

vi.mock("@frutti/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@frutti/api")>();
  return {
    ...actual,
    createSale: vi.fn(),
    addMyExpense: vi.fn(),
    collectMyPayment: vi.fn(),
    reportMyLoss: vi.fn(),
    reportSyncProblem: vi.fn(),
  };
});

vi.mock("./queue", async (importOriginal) => ({
  // `madeAtOf` is a plain function: the real one is used.
  ...(await importOriginal<typeof import("./queue")>()),
  listQueue: vi.fn(),
  markRefused: vi.fn(),
  markReported: vi.fn(),
  removeQueued: vi.fn(),
}));

const queryClient = { invalidateQueries: vi.fn() } as unknown as QueryClient;

function sale(uuid: string, status: "pending" | "refused" = "pending"): QueuedSale {
  return {
    kind: "sale",
    uuid,
    createdAt: `2026-10-13T08:0${uuid}:00.000Z`,
    label: "Client test",
    status,
    error: "",
    data: {
      customer: null,
      location: 1,
      confirm_now: true,
      client_uuid: uuid,
      amount_paid: "10.000",
      payment_method: "cash",
      lines: [],
      boxes: { small: 0, big: 0 },
    } as unknown as QueuedSale["data"],
    estimate: { lines: [], total: "10.000", paid: "10.000" },
  };
}

function setOnline(online: boolean) {
  vi.stubGlobal("navigator", { onLine: online });
}

beforeEach(() => {
  setOnline(true);
  vi.mocked(listQueue).mockReset();
  vi.mocked(createSale).mockReset();
  vi.mocked(reportSyncProblem)
    .mockReset()
    .mockResolvedValue({} as never);
  vi.mocked(removeQueued).mockReset().mockResolvedValue(undefined);
  vi.mocked(markRefused).mockReset().mockResolvedValue(undefined);
  vi.mocked(markReported).mockReset().mockResolvedValue(undefined);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("a sale the server takes is removed from the queue", async () => {
  vi.mocked(listQueue).mockResolvedValue([sale("1")]);
  vi.mocked(createSale).mockResolvedValue({} as never);

  await sendWaiting(queryClient);

  expect(removeQueued).toHaveBeenCalledWith("1");
  expect(getSyncProblem()).toBeNull();
});

test("no connection keeps the sale pending and says why", async () => {
  vi.mocked(listQueue).mockResolvedValue([sale("1")]);
  vi.mocked(createSale).mockRejectedValue(new TypeError("Failed to fetch"));

  await sendWaiting(queryClient);

  expect(removeQueued).not.toHaveBeenCalled();
  expect(markRefused).not.toHaveBeenCalled();
  expect(getSyncProblem()).toBe("offline");
});

test("a refusal by the server (day approved, 403) makes the sale refused, not pending", async () => {
  vi.mocked(listQueue).mockResolvedValue([sale("1")]);
  vi.mocked(createSale).mockRejectedValue(
    new ApiError(403, "Votre journée est approuvée par le bureau : elle est fermée.", {
      detail: "Votre journée est approuvée par le bureau : elle est fermée.",
    }),
  );

  await sendWaiting(queryClient);

  expect(markRefused).toHaveBeenCalledWith(
    expect.objectContaining({ uuid: "1" }),
    "Votre journée est approuvée par le bureau : elle est fermée.",
  );
  expect(removeQueued).not.toHaveBeenCalled();
  expect(reportSyncProblem).toHaveBeenCalledTimes(1);
});

test("a waiting sale is sent with the time it was made, not the time it is sent (D-133)", async () => {
  const made = { ...sale("1"), createdAt: "2026-10-12T14:00:00.000Z" };
  made.data = { ...made.data, sold_at: "2026-10-12T14:00:00.000Z" };
  vi.mocked(listQueue).mockResolvedValue([made]);
  vi.mocked(createSale).mockResolvedValue({} as never);
  vi.useFakeTimers({ now: new Date("2026-10-13T07:30:00.000Z") });

  await sendWaiting(queryClient);

  expect(createSale).toHaveBeenCalledWith(
    expect.objectContaining({ client_uuid: "1", sold_at: "2026-10-12T14:00:00.000Z" }),
    expect.anything(),
  );
  expect(removeQueued).toHaveBeenCalledWith("1");
});

test("a sale kept by an earlier version of the app, without a time, takes the time it was put in the queue", async () => {
  const old = { ...sale("1"), createdAt: "2026-10-12T16:45:00.000Z" };
  expect(old.data.sold_at).toBeUndefined();
  vi.mocked(listQueue).mockResolvedValue([old]);
  vi.mocked(createSale).mockResolvedValue({} as never);

  await sendWaiting(queryClient);

  expect(createSale).toHaveBeenCalledWith(
    expect.objectContaining({ client_uuid: "1", sold_at: "2026-10-12T16:45:00.000Z" }),
    expect.anything(),
  );
});

test("a sale of an earlier day the office approved (403) is refused and reported, it does not wait for ever", async () => {
  const reason = "Votre journée du 12/10/2026 est approuvée par le bureau : elle est fermée, plus rien ne s'y ajoute.";
  vi.mocked(listQueue).mockResolvedValue([sale("1"), sale("2")]);
  vi.mocked(createSale)
    .mockRejectedValueOnce(new ApiError(403, reason, { detail: reason }))
    .mockResolvedValue({} as never);

  await sendWaiting(queryClient);

  expect(markRefused).toHaveBeenCalledWith(expect.objectContaining({ uuid: "1" }), reason);
  expect(reportSyncProblem).toHaveBeenCalledWith({ kind: "sale", what: "Client test", reason, client_uuid: "1" });
  // The next sale is still sent: one refusal does not block the queue.
  expect(removeQueued).toHaveBeenCalledWith("2");
  expect(getSyncProblem()).toBeNull();
});

test("a sale made after the day was sent (403, D-134) ends refused and reported, never pending", async () => {
  const reason = "Votre journée est clôturée : elle rouvre quand le bureau recharge votre camion.";
  vi.mocked(listQueue).mockResolvedValue([sale("1"), sale("2")]);
  vi.mocked(createSale)
    .mockRejectedValueOnce(new ApiError(403, reason, { detail: reason }))
    .mockResolvedValue({} as never);

  await sendWaiting(queryClient);

  expect(markRefused).toHaveBeenCalledWith(expect.objectContaining({ uuid: "1", status: "pending" }), reason);
  expect(reportSyncProblem).toHaveBeenCalledWith({ kind: "sale", what: "Client test", reason, client_uuid: "1" });
  expect(removeQueued).toHaveBeenCalledWith("2");
  expect(getSyncProblem()).toBeNull();
});

test("a sale dated in the future by a wrong phone clock (400) is refused and reported with the server's words", async () => {
  const reason = "Cette vente est datée dans le futur (14/10/2026 09:00) : vérifiez la date et l'heure du téléphone.";
  vi.mocked(listQueue).mockResolvedValue([sale("1")]);
  vi.mocked(createSale).mockRejectedValue(new ApiError(400, "Erreur 400", { sold_at: [reason] }));

  await sendWaiting(queryClient);

  expect(markRefused).toHaveBeenCalledWith(expect.objectContaining({ uuid: "1" }), reason);
  expect(reportSyncProblem).toHaveBeenCalledTimes(1);
  expect(removeQueued).not.toHaveBeenCalled();
});

test("a session that ended (401) keeps the sale pending, stops, and says the session ended", async () => {
  vi.mocked(listQueue).mockResolvedValue([sale("1"), sale("2")]);
  vi.mocked(createSale).mockRejectedValue(new ApiError(401, "Non connecté", { detail: "Non connecté" }));

  await sendWaiting(queryClient);

  expect(createSale).toHaveBeenCalledTimes(1);
  expect(markRefused).not.toHaveBeenCalled();
  expect(getSyncProblem()).toBe("session");
});

test("a server that is busy or behind a restarting proxy (503) keeps the sale pending, it is not refused", async () => {
  vi.mocked(listQueue).mockResolvedValue([sale("1"), sale("2")]);
  vi.mocked(createSale).mockRejectedValue(new ApiError(503, "Erreur 503", "<html>503 Service Unavailable</html>"));

  await sendWaiting(queryClient);

  expect(markRefused).not.toHaveBeenCalled();
  expect(removeQueued).not.toHaveBeenCalled();
  expect(createSale).toHaveBeenCalledTimes(1);
  expect(getSyncProblem()).toBe("server");
});

test("a request that never answers does not stop the next sync", async () => {
  vi.useFakeTimers();
  vi.mocked(listQueue).mockResolvedValue([sale("1")]);
  // The phone stays "online" but the answer never comes (weak signal): the first run must give up by itself.
  vi.mocked(createSale).mockImplementationOnce(() => new Promise<never>(() => undefined));

  const first = sendWaiting(queryClient);
  await vi.advanceTimersByTimeAsync(SEND_TIMEOUT_MS);
  await first;
  expect(getSyncProblem()).toBe("offline");

  vi.mocked(createSale).mockResolvedValue({} as never);
  await sendWaiting(queryClient);
  expect(createSale).toHaveBeenCalledTimes(2);
  expect(removeQueued).toHaveBeenCalledWith("1");
});

test("nothing is sent while the phone says it is offline", async () => {
  setOnline(false);
  vi.mocked(listQueue).mockResolvedValue([sale("1")]);

  await sendWaiting(queryClient);

  expect(createSale).not.toHaveBeenCalled();
  expect(getSyncProblem()).toBe("offline");
});
