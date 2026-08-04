import { describe, expect, it } from "vitest";

import {
  enforceApiTransport,
  isLoopbackHostname,
} from "../src/lib/transportSecurity";

describe("inference transport policy", () => {
  it("allows HTTP only on explicit loopback hosts", () => {
    expect(
      enforceApiTransport("http://127.0.0.1:8000/v1/analyze").isLoopback,
    ).toBe(true);
    expect(enforceApiTransport("http://[::1]:8000/v1/analyze").isLoopback).toBe(
      true,
    );
    expect(isLoopbackHostname("127.23.4.5")).toBe(true);
  });

  it("requires HTTPS outside loopback", () => {
    expect(() =>
      enforceApiTransport("http://api.example.test/v1/analyze"),
    ).toThrow(/HTTPS/);
    expect(
      enforceApiTransport("https://api.example.test/v1/analyze").isLoopback,
    ).toBe(false);
  });
});
