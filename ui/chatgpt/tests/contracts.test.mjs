// Challenge the presentation boundary with malformed envelopes and untrusted
// strings; server authorization and archive integrity have separate test suites.
import assert from "node:assert/strict";
import test from "node:test";
import { associationLabel, collectionRef, integer, items, portalUrl, responseData } from "../src/contracts.ts";

test("accepts only the current successful server envelope", () => {
  assert.deepEqual(responseData({ structuredContent: { response_version: 2, status: "ok", data: { count: 3 } } }), { count: 3 });
  for (const value of [undefined, {}, { response_version: 1 }, { response_version: 2, status: "ok", data: [] }]) {
    assert.throws(() => responseData({ structuredContent: value }));
  }
});

test("does not render a server exception containing private filesystem details", () => {
  assert.throws(() => responseData({ structuredContent: {
    response_version: 2, status: "error", error_code: "internal_error", message: "/private/customer/source.txt",
  } }), (error) => !error.message.includes("/private"));
});

test("bounds pages, identifiers, and exact integer counts", () => {
  assert.throws(() => items(Array(101).fill({})));
  assert.throws(() => integer(1.5));
  assert.throws(() => integer(-1));
  assert.throws(() => collectionRef({ collection_id: "x".repeat(129), generation: "a" }));
});

test("portal address accepts trusted HTTPS or local development without embedded credentials", () => {
  assert.equal(portalUrl("https://keepmorrow.example/portal"), "https://keepmorrow.example/portal");
  assert.equal(portalUrl("http://127.0.0.1:8765/portal"), "http://127.0.0.1:8765/portal");
  for (const value of ["javascript:alert(1)", "data:text/html,script", "https://user:secret@example.com", "https://example.com/?token=private", "http://example.com/portal", "https://example.com/#secret"]) {
    assert.throws(() => portalUrl(value));
  }
});

test("unknown project association remains distinct from confirmed standalone", () => {
  assert.equal(associationLabel({ state: "association_unknown" }), "Project association unknown");
  assert.equal(associationLabel({ state: "standalone_confirmed" }), "Confirmed standalone");
  assert.throws(() => associationLabel({ state: "probably_standalone" }));
});
