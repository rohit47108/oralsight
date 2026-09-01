import { describe, expect, it } from "vitest";

import {
  buildSyncEntities,
  mergeRemoteChanges,
  stableJson,
  syncEntityFingerprint,
} from "../src/cloud/syncModel";
import type { PersistedAppState } from "../src/types";

const emptyState: PersistedAppState = {
  schemaVersion: 4,
  consentedAt: null,
  profile: null,
  settings: {
    highContrast: false,
    largeText: false,
    reducedMotion: false,
    animationSpeed: "standard",
    haptics: true,
    voiceInstructions: false,
    caregiverMode: false,
    analyticsOptIn: false,
  },
  sessions: [],
  captures: [],
  analyses: {},
  comparisons: [],
  pins: [],
  reports: [],
  activeSessionId: null,
};

describe("local-first encrypted sync model", () => {
  it("uses canonical object ordering for change fingerprints", () => {
    expect(stableJson({ b: 2, a: { d: 4, c: 3 } })).toBe(
      '{"a":{"c":3,"d":4},"b":2}',
    );
    expect(syncEntityFingerprint({ a: 1, b: 2 })).toBe(
      syncEntityFingerprint({ b: 2, a: 1 }),
    );
  });

  it("never places a device-local vault path into a synced capture payload", () => {
    const state: PersistedAppState = {
      ...emptyState,
      sessions: [
        {
          id: "session-1",
          createdAt: "2026-08-06T12:00:00.000Z",
          demo: false,
          label: "Structured scan",
          protocol: "standard_eight_region",
        },
      ],
      captures: [
        {
          id: "capture-1",
          sessionId: "session-1",
          region: "upper_lip",
          angle: "primary",
          mediaKind: "image",
          capturedAt: "2026-08-06T12:01:00.000Z",
          encryptedUri: "file:///private/stoma3d-vault/secret.osv",
          mimeType: "image/jpeg",
          inputOrigin: "live_capture",
          captureSource: "camera",
          privacyConfirmedByUser: true,
          regionConfirmedByUser: true,
          quality: {
            accepted: true,
            blurScore: 0.9,
            exposureScore: 0.9,
            glareScore: 0.1,
            obstructionScore: 0.1,
            faceDetected: false,
            reasons: [],
          },
        },
      ],
    };
    const capture = buildSyncEntities(state).find(
      (entity) => entity.entityType === "capture_view",
    );
    expect(capture?.payload).toMatchObject({ encryptedUri: null });
    expect(JSON.stringify(capture)).not.toContain("file:///private");
  });

  it("applies parent records before child records and keeps cloud references out of local state", () => {
    const session = {
      id: "session-remote",
      createdAt: "2026-08-06T12:00:00.000Z",
      demo: false,
      label: "Remote scan",
      protocol: "standard_eight_region" as const,
    };
    const capture = {
      id: "capture-remote",
      sessionId: session.id,
      region: "upper_lip" as const,
      angle: "primary" as const,
      mediaKind: "image" as const,
      capturedAt: "2026-08-06T12:01:00.000Z",
      encryptedUri: null,
      mimeType: "image/jpeg" as const,
      inputOrigin: "live_capture" as const,
      captureSource: "camera" as const,
      privacyConfirmedByUser: true,
      regionConfirmedByUser: true,
      quality: {
        accepted: true,
        blurScore: 0.9,
        exposureScore: 0.9,
        glareScore: 0.1,
        obstructionScore: 0.1,
        faceDetected: false,
        reasons: [],
      },
    };
    const merged = mergeRemoteChanges(emptyState, [
      {
        entityType: "capture_view",
        entityId: capture.id,
        operation: "upsert",
        payload: {
          schemaVersion: 1,
          entityType: "capture_view",
          entityId: capture.id,
          record: capture,
          cloudRefs: {
            kind: "capture_view",
            localId: capture.id,
            remoteId: "remote-view-id",
          },
        },
        version: 1,
        serverSequence: 2,
      },
      {
        entityType: "scan_session",
        entityId: session.id,
        operation: "upsert",
        payload: {
          schemaVersion: 1,
          entityType: "scan_session",
          entityId: session.id,
          record: session,
        },
        version: 1,
        serverSequence: 1,
      },
    ]);
    expect(merged.sessions).toEqual([session]);
    expect(merged.captures).toEqual([capture]);
    expect(JSON.stringify(merged)).not.toContain("remote-view-id");
  });

  it("makes a remote tombstone authoritative", () => {
    const state: PersistedAppState = {
      ...emptyState,
      sessions: [
        {
          id: "session-1",
          createdAt: "2026-08-06T12:00:00.000Z",
          demo: false,
          label: "Scan",
          protocol: "standard_eight_region",
        },
      ],
    };
    expect(
      mergeRemoteChanges(state, [
        {
          entityType: "scan_session",
          entityId: "session-1",
          operation: "delete",
          payload: null,
          version: 2,
          serverSequence: 4,
        },
      ]).sessions,
    ).toEqual([]);
  });
});
