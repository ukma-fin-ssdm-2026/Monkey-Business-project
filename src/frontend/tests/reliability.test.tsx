import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../src/api/client";
import { fetchAllCards } from "../src/pages/BoardPage";
import { CardModal } from "../src/components/CardModal";

vi.mock("../src/context/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "user-1", email: "user@example.com", role: "candidate", is_active: true },
  }),
}));

const card = {
  id: "card-1",
  board_id: "board-1",
  stage_id: "stage-1",
  company: "Acme",
  position: "Engineer",
  vacancy_url: null,
  requirements_text: null,
  deadline: null,
  notifications_enabled: false,
  status: "active" as const,
  position_index: 0,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("frontend reliability fixes", () => {
  it("fails with a safe timeout message when an API request is aborted", async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => (
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"));
        });
      })
    ) as Promise<Response>);

    const request = expect(
      api.login({ email: "user@example.com", password: "password" }),
    ).rejects.toThrow("API не відповів вчасно");
    await act(async () => {
      vi.advanceTimersByTime(10_000);
    });

    await request;
  });

  it("turns a non-JSON API response into a controlled HTTP error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("<html>bad gateway</html>", {
        status: 502,
        headers: { "Content-Type": "text/html" },
      }),
    );

    await expect(api.login({ email: "user@example.com", password: "password" }))
      .rejects.toThrow("Запит не вдався: HTTP 502");
  });

  it("stops pagination when the API repeats a page without progress", async () => {
    vi.spyOn(api, "listCards").mockResolvedValue({
      items: [card],
      pagination: { limit: 100, offset: 0, total: 2 },
    });

    await expect(fetchAllCards("board-1"))
      .rejects.toThrow("без нового прогресу");
    expect(api.listCards).toHaveBeenCalledTimes(2);
  });
});

describe("CardModal reliability fallback", () => {
  it("shows dependent-data failures instead of presenting empty data", async () => {
    vi.spyOn(api, "listLinks").mockRejectedValue(new Error("links unavailable"));
    vi.spyOn(api, "listNotes").mockRejectedValue(new Error("notes unavailable"));
    vi.spyOn(api, "listComments").mockResolvedValue([]);
    vi.spyOn(api, "listMentors").mockRejectedValue(new Error("mentors unavailable"));

    render(
      <CardModal
        boardId="board-1"
        card={card}
        canWrite={false}
        onClose={vi.fn()}
        onUpdated={vi.fn()}
        onDeleted={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getAllByRole("alert")).toHaveLength(3);
    });
    expect(screen.queryByText("Ще немає посилань")).toBeNull();
    expect(screen.queryByText("Ще немає нотаток")).toBeNull();
    expect(screen.getAllByRole("button", { name: "Повторити" })).toHaveLength(3);
  });
});
