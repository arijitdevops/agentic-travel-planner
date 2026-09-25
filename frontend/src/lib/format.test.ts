import { describe, expect, it } from "vitest";
import { addDays, clock, dayOffset, duration, money, nightsBetween, splitNights, stopsLabel } from "./format";
import { errorMessage } from "../api/client";

describe("format helpers", () => {
  it("formats money and durations", () => {
    expect(money(1234.5)).toBe("$1,235");
    expect(money(99.5, "USD", 2)).toBe("$99.50");
    expect(duration(445)).toBe("7h 25m");
    expect(duration(45)).toBe("45m");
  });

  it("handles dates", () => {
    expect(clock("2030-06-01T09:05:00")).toBe("09:05");
    expect(nightsBetween("2030-06-01", "2030-06-06")).toBe(5);
    expect(addDays("2030-12-30", 3)).toBe("2031-01-02");
    expect(dayOffset("2030-06-01T22:00:00", "2030-06-02T06:00:00")).toBe(1);
  });

  it("labels stops", () => {
    expect(stopsLabel(0, null)).toBe("Nonstop");
    expect(stopsLabel(1, "SIN")).toBe("1 stop via SIN");
  });

  it("splits nights like the backend", () => {
    expect(splitNights(7, 3)).toEqual([3, 2, 2]);
    expect(splitNights(4, 1)).toEqual([4]);
  });
});

describe("errorMessage", () => {
  it("reads FastAPI error bodies", () => {
    expect(errorMessage({ detail: "Trip not found" }, "x")).toBe("Trip not found");
    expect(errorMessage({ detail: [{ loc: ["body", "budget"], msg: "must be > 0" }] }, "x")).toBe("budget: must be > 0");
    expect(errorMessage(null, "fallback")).toBe("fallback");
  });
});
