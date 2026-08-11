"use client";

import {
  useActionState,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from "react";

import {
  createAnnotationAction,
  type ReviewActionState,
} from "@/app/clinician/reviews/actions";
import {
  clientPointToNormalized,
  extractOutlineTargets,
  insertPolygonPoint,
  movePolygonPoint,
  nudgePolygonPoint,
  parseOutlineAdjustment,
  removePolygonPoint,
  serializeOutlineAdjustment,
  type NormalizedPoint,
  type OutlineAdjustmentPayload,
  type OutlineTarget,
} from "@/components/outline-adjustment";
import type {
  ResourceRef,
  ResourceView,
  ReviewAnnotation,
} from "@/lib/platform-api";
import { readableLabel } from "@/lib/presentation";

const initialActionState: ReviewActionState = { status: "idle" };

function latestSavedOutline(
  annotations: ReviewAnnotation[],
  resource: ResourceRef,
  target: OutlineTarget,
): OutlineAdjustmentPayload | null {
  for (let index = annotations.length - 1; index >= 0; index -= 1) {
    const annotation = annotations[index];
    if (
      annotation?.kind !== "outline_adjustment" ||
      annotation.resource.resourceType !== resource.resourceType ||
      annotation.resource.resourceId !== resource.resourceId
    ) {
      continue;
    }
    const parsed = parseOutlineAdjustment(annotation.body);
    if (
      parsed?.observationId === target.observationId &&
      parsed.captureViewId === target.captureViewId
    ) {
      return parsed;
    }
  }
  return null;
}

function EditorWorkspace({
  reviewId,
  resource,
  target,
  saved,
  operationKey,
}: {
  reviewId: string;
  resource: ResourceRef;
  target: OutlineTarget;
  saved: OutlineAdjustmentPayload | null;
  operationKey: string;
}) {
  const sourcePolygon = saved?.polygon ?? target.modelPolygon;
  const sourceNote = saved?.note ?? "";
  const [polygon, setPolygon] = useState<NormalizedPoint[]>(sourcePolygon);
  const [note, setNote] = useState(sourceNote);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [imageAspectRatio, setImageAspectRatio] = useState(4 / 3);
  const [imageFailed, setImageFailed] = useState(false);
  const [state, action, pending] = useActionState(
    createAnnotationAction,
    initialActionState,
  );
  const stageRef = useRef<HTMLDivElement>(null);
  const draggingPointer = useRef<number | null>(null);
  const body = serializeOutlineAdjustment({ target, polygon, note });
  const sourceBody = serializeOutlineAdjustment({
    target,
    polygon: sourcePolygon,
    note: sourceNote,
  });
  const dirty = body !== sourceBody;
  const selectedPoint = polygon[selectedIndex] ?? polygon[0]!;

  const setPoint = (index: number, point: NormalizedPoint) => {
    setPolygon((current) => movePolygonPoint(current, index, point));
  };

  const pointFromPointer = (event: PointerEvent<HTMLButtonElement>) => {
    const bounds = stageRef.current?.getBoundingClientRect();
    return bounds
      ? clientPointToNormalized(bounds, event.clientX, event.clientY)
      : null;
  };

  const handleKey = (
    event: KeyboardEvent<HTMLButtonElement>,
    pointIndex: number,
  ) => {
    const step = event.shiftKey ? 0.02 : 0.005;
    const delta: Record<string, NormalizedPoint> = {
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
      ArrowUp: [0, -step],
      ArrowDown: [0, step],
    };
    const change = delta[event.key];
    if (!change) return;
    event.preventDefault();
    setSelectedIndex(pointIndex);
    setPolygon((current) =>
      nudgePolygonPoint(current, pointIndex, change[0], change[1]),
    );
  };

  return (
    <form className="outline-editor" action={action}>
      <input type="hidden" name="operationKey" value={operationKey} />
      <input type="hidden" name="reviewId" value={reviewId} />
      <input type="hidden" name="resourceType" value={resource.resourceType} />
      <input type="hidden" name="resourceId" value={resource.resourceId} />
      <input type="hidden" name="kind" value="outline_adjustment" />
      <input type="hidden" name="body" value={body} />

      <div
        ref={stageRef}
        className="outline-editor__stage"
        style={{ aspectRatio: imageAspectRatio }}
        data-image-state={imageFailed ? "failed" : "ready"}
      >
        {/* The protected BFF route is authenticated and intentionally bypasses
            public image optimization and caching. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`/api/clinician/reviews/${encodeURIComponent(reviewId)}/capture-views/${encodeURIComponent(target.captureViewId)}/content`}
          alt={`Patient-authorized capture for ${readableLabel(target.region)} outline review.`}
          draggable={false}
          onLoad={(event) => {
            const { naturalHeight, naturalWidth } = event.currentTarget;
            if (naturalHeight > 0 && naturalWidth > 0) {
              setImageAspectRatio(naturalWidth / naturalHeight);
            }
            setImageFailed(false);
          }}
          onError={() => setImageFailed(true)}
        />
        <svg
          aria-hidden="true"
          className="outline-editor__overlay"
          viewBox="0 0 1000 1000"
          preserveAspectRatio="none"
        >
          <polygon
            points={polygon
              .map(
                ([x, y]) => `${(x * 1000).toFixed(2)},${(y * 1000).toFixed(2)}`,
              )
              .join(" ")}
          />
        </svg>
        {polygon.map(([x, y], pointIndex) => (
          <button
            key={`${pointIndex}:${polygon.length}`}
            type="button"
            className="outline-editor__handle"
            style={{ left: `${x * 100}%`, top: `${y * 100}%` }}
            aria-label={`Outline point ${pointIndex + 1} of ${polygon.length}. X ${(x * 100).toFixed(1)} percent, Y ${(y * 100).toFixed(1)} percent.`}
            aria-describedby="outline-editor-instructions"
            aria-pressed={selectedIndex === pointIndex}
            onClick={() => setSelectedIndex(pointIndex)}
            onKeyDown={(event) => handleKey(event, pointIndex)}
            onPointerDown={(event) => {
              setSelectedIndex(pointIndex);
              draggingPointer.current = event.pointerId;
              event.currentTarget.setPointerCapture(event.pointerId);
            }}
            onPointerMove={(event) => {
              if (draggingPointer.current !== event.pointerId) return;
              const point = pointFromPointer(event);
              if (point) setPoint(pointIndex, point);
            }}
            onPointerUp={(event) => {
              if (draggingPointer.current === event.pointerId) {
                draggingPointer.current = null;
                event.currentTarget.releasePointerCapture(event.pointerId);
              }
            }}
            onPointerCancel={() => {
              draggingPointer.current = null;
            }}
          >
            <span>{pointIndex + 1}</span>
          </button>
        ))}
        {imageFailed ? (
          <div className="outline-editor__image-error" role="alert">
            The authorized capture could not be loaded. The saved analysis was
            not changed.
          </div>
        ) : null}
      </div>

      <p id="outline-editor-instructions" className="form-help">
        Drag a numbered point, or focus it and use the arrow keys. Hold Shift
        for a larger keyboard step. Coordinates stay normalized to this image.
      </p>

      <div className="outline-editor__point-controls">
        <div aria-live="polite" className="outline-editor__coordinate-readout">
          <strong>Point {selectedIndex + 1}</strong>
          <label>
            X percent
            <input
              type="number"
              min="0"
              max="100"
              step="0.1"
              value={(selectedPoint[0] * 100).toFixed(1)}
              onChange={(event) => {
                const value = Number(event.currentTarget.value);
                if (Number.isFinite(value)) {
                  setPoint(selectedIndex, [value / 100, selectedPoint[1]]);
                }
              }}
            />
          </label>
          <label>
            Y percent
            <input
              type="number"
              min="0"
              max="100"
              step="0.1"
              value={(selectedPoint[1] * 100).toFixed(1)}
              onChange={(event) => {
                const value = Number(event.currentTarget.value);
                if (Number.isFinite(value)) {
                  setPoint(selectedIndex, [selectedPoint[0], value / 100]);
                }
              }}
            />
          </label>
        </div>
        <div className="outline-editor__edit-buttons">
          <button
            className="text-button"
            type="button"
            disabled={polygon.length >= 96}
            onClick={() => {
              setPolygon((current) =>
                insertPolygonPoint(current, selectedIndex),
              );
              setSelectedIndex((current) => current + 1);
            }}
          >
            Add point after
          </button>
          <button
            className="text-button"
            type="button"
            disabled={polygon.length <= 3}
            onClick={() => {
              setPolygon((current) =>
                removePolygonPoint(current, selectedIndex),
              );
              setSelectedIndex((current) =>
                Math.max(0, Math.min(current - 1, polygon.length - 2)),
              );
            }}
          >
            Remove point
          </button>
          <button
            className="text-button"
            type="button"
            onClick={() => {
              setPolygon(target.modelPolygon);
              setSelectedIndex(0);
            }}
          >
            Reset to model outline
          </button>
          {dirty ? (
            <button
              className="text-button"
              type="button"
              onClick={() => {
                setPolygon(sourcePolygon);
                setNote(sourceNote);
                setSelectedIndex(0);
              }}
            >
              Undo unsaved edits
            </button>
          ) : null}
        </div>
      </div>

      <label className="outline-editor__note">
        Correction note <span>Optional</span>
        <textarea
          value={note}
          maxLength={600}
          onChange={(event) => setNote(event.currentTarget.value)}
          placeholder="Briefly explain what you changed or why the model outline was inaccurate."
        />
      </label>
      <div className="outline-editor__footer">
        <p>
          This saves a clinician-authored correction beside the original model
          output. It does not overwrite the analysis or retrain a model.
        </p>
        <button
          className="button"
          type="submit"
          disabled={pending || !operationKey || !dirty || imageFailed}
        >
          {pending ? "Saving…" : "Save corrected outline"}
        </button>
      </div>
      {state.status !== "idle" ? (
        <p
          className="form-message"
          role="status"
          data-state={state.status === "error" ? "error" : "saved"}
        >
          {state.message}
        </p>
      ) : null}
    </form>
  );
}

export function OutlineAdjustmentEditor({
  reviewId,
  resource,
  resourceView,
  annotations,
  operationKey,
}: {
  reviewId: string;
  resource: ResourceRef;
  resourceView: ResourceView;
  annotations: ReviewAnnotation[];
  operationKey: string;
}) {
  const targets = useMemo(
    () =>
      resource.resourceType === "analysis_run"
        ? extractOutlineTargets(resourceView.data)
        : [],
    [resource.resourceType, resourceView.data],
  );
  const [selectedObservationId, setSelectedObservationId] = useState(
    targets[0]?.observationId ?? "",
  );
  const target =
    targets.find((item) => item.observationId === selectedObservationId) ??
    targets[0];
  if (!target) return null;
  const saved = latestSavedOutline(annotations, resource, target);

  return (
    <section
      className="outline-editor-shell"
      aria-labelledby="outline-editor-title"
    >
      <header className="outline-editor-shell__heading">
        <div>
          <p className="workspace-kicker">Visual correction</p>
          <h3 id="outline-editor-title">Adjust the candidate outline</h3>
          <p>
            Review the model boundary on the exact patient-authorized capture.
          </p>
        </div>
        {targets.length > 1 ? (
          <label>
            Observation
            <select
              value={target.observationId}
              onChange={(event) =>
                setSelectedObservationId(event.currentTarget.value)
              }
            >
              {targets.map((item, index) => (
                <option key={item.observationId} value={item.observationId}>
                  {index + 1}. {readableLabel(item.region)}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <span>{readableLabel(target.region)}</span>
        )}
      </header>
      <EditorWorkspace
        key={`${target.observationId}:${saved ? serializeOutlineAdjustment({ target, polygon: saved.polygon, note: saved.note ?? "" }) : "model"}`}
        reviewId={reviewId}
        resource={resource}
        target={target}
        saved={saved}
        operationKey={operationKey}
      />
    </section>
  );
}
