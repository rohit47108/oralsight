import { ReportFileViewer } from "@/components/report-file-viewer";
import type { ResourceView } from "@/lib/platform-api";
import { readableDate, readableLabel } from "@/lib/presentation";

type UnknownRecord = Record<string, unknown>;
type LedgerItem = { label: string; value: string };

const REPORT_FORMATS = new Set([
  "pdf",
  "html",
  "fhir_r4_bundle",
  "summary_video",
  "transcript",
]);

function record(value: unknown): UnknownRecord | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as UnknownRecord)
    : null;
}

function string(value: unknown): string | null {
  return typeof value === "string" && value.length ? value : null;
}

function number(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function strings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function records(value: unknown): UnknownRecord[] {
  return Array.isArray(value)
    ? value.flatMap((item) => {
        const parsed = record(item);
        return parsed ? [parsed] : [];
      })
    : [];
}

function percentage(value: unknown): string | null {
  const parsed = number(value);
  return parsed === null ? null : `${Math.round(parsed * 100)}%`;
}

function date(value: unknown): string | null {
  const parsed = string(value);
  return parsed ? readableDate(parsed) : null;
}

function fileSize(value: unknown): string | null {
  const parsed = number(value);
  if (parsed === null) return null;
  if (parsed < 1024) return `${parsed} bytes`;
  if (parsed < 1024 * 1024) return `${(parsed / 1024).toFixed(1)} KB`;
  return `${(parsed / 1024 / 1024).toFixed(1)} MB`;
}

function displayLabel(value: unknown): string | null {
  const parsed = string(value);
  return parsed ? readableLabel(parsed) : null;
}

function Ledger({ items }: { items: Array<LedgerItem | null> }) {
  const available = items.filter((item): item is LedgerItem => item !== null);
  if (!available.length) return null;
  return (
    <dl className="authorized-resource__ledger">
      {available.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Limitations({ values }: { values: string[] }) {
  if (!values.length) return null;
  return (
    <div className="authorized-resource__limitations">
      <h4>Recorded limitations</h4>
      <ul>
        {values.map((value, index) => (
          <li key={`${index}:${value}`}>{value}</li>
        ))}
      </ul>
    </div>
  );
}

function ModelOutput({
  title,
  value,
  experimental = false,
}: {
  title: string;
  value: unknown;
  experimental?: boolean;
}) {
  const output = record(value);
  if (!output) return null;
  const enabled = output.enabled === true;
  const label = displayLabel(output.topLabel);
  const confidence = percentage(output.confidence);
  const limitation = string(output.limitation);
  return (
    <section className="authorized-model-output" data-enabled={enabled}>
      <div>
        <h4>{title}</h4>
        <span>{enabled ? "Released output" : "Not released"}</span>
      </div>
      {enabled && label ? (
        <p>
          <strong>{label}</strong>
          {confidence ? `, ${confidence} confidence` : ""}
        </p>
      ) : null}
      {limitation ? <p>{limitation}</p> : null}
      {experimental ? (
        <p className="authorized-model-output__note">
          This research output does not determine care guidance.
        </p>
      ) : null}
    </section>
  );
}

function Observation({
  value,
  index,
}: {
  value: UnknownRecord;
  index: number;
}) {
  const descriptors = record(value.descriptors);
  const uncertainty = record(value.uncertainty);
  const calibration = record(value.calibration);
  const calibrated = calibration?.status === "valid";
  const limitations = [
    ...strings(value.limitations),
    ...strings(uncertainty?.limitations),
  ];
  const region = displayLabel(value.region) ?? `Observation ${index + 1}`;
  return (
    <details className="authorized-observation" open={index === 0}>
      <summary>
        <span>{region}</span>
        <small>{string(value.observationId) ?? "Candidate observation"}</small>
      </summary>
      <div className="authorized-observation__body">
        <Ledger
          items={[
            displayLabel(value.anatomicalSite)
              ? {
                  label: "Anatomical site",
                  value: displayLabel(value.anatomicalSite)!,
                }
              : null,
            percentage(descriptors?.normalizedArea)
              ? {
                  label: "Image area",
                  value: `${percentage(descriptors?.normalizedArea)} approximate`,
                }
              : null,
            number(descriptors?.borderIrregularity) !== null
              ? {
                  label: "Border irregularity",
                  value: number(descriptors?.borderIrregularity)!.toFixed(3),
                }
              : null,
            percentage(descriptors?.meanRedness)
              ? {
                  label: "Mean redness",
                  value: percentage(descriptors?.meanRedness)!,
                }
              : null,
            percentage(descriptors?.meanBrightness)
              ? {
                  label: "Mean brightness",
                  value: percentage(descriptors?.meanBrightness)!,
                }
              : null,
            percentage(descriptors?.textureContrast)
              ? {
                  label: "Texture contrast",
                  value: percentage(descriptors?.textureContrast)!,
                }
              : null,
            percentage(uncertainty?.overallConfidence)
              ? {
                  label: "Overall confidence",
                  value: percentage(uncertainty?.overallConfidence)!,
                }
              : null,
            percentage(uncertainty?.imageQualityConfidence)
              ? {
                  label: "Image quality confidence",
                  value: percentage(uncertainty?.imageQualityConfidence)!,
                }
              : null,
            string(value.namedMesh)
              ? {
                  label: "Observation map mesh",
                  value: string(value.namedMesh)!,
                }
              : null,
            string(value.assetVersion)
              ? {
                  label: "Map asset version",
                  value: string(value.assetVersion)!,
                }
              : null,
          ]}
        />
        {calibration ? (
          <section className="authorized-calibration" data-valid={calibrated}>
            <div>
              <h4>Physical calibration</h4>
              <span>
                {calibrated ? "Valid for this capture" : "No valid scale"}
              </span>
            </div>
            {calibrated ? (
              <Ledger
                items={[
                  number(calibration.estimatedWidthMm) !== null
                    ? {
                        label: "Estimated width",
                        value: `${number(calibration.estimatedWidthMm)!.toFixed(1)} mm`,
                      }
                    : null,
                  number(calibration.estimatedHeightMm) !== null
                    ? {
                        label: "Estimated height",
                        value: `${number(calibration.estimatedHeightMm)!.toFixed(1)} mm`,
                      }
                    : null,
                  number(calibration.estimatedAreaMm2) !== null
                    ? {
                        label: "Estimated area",
                        value: `${number(calibration.estimatedAreaMm2)!.toFixed(1)} mm²`,
                      }
                    : null,
                  percentage(calibration.confidence)
                    ? {
                        label: "Calibration confidence",
                        value: percentage(calibration.confidence)!,
                      }
                    : null,
                ]}
              />
            ) : null}
            <p>Calibrated estimates are approximate.</p>
          </section>
        ) : null}
        <ModelOutput title="Appearance output" value={value.appearanceOutput} />
        <ModelOutput
          title="Experimental research output"
          value={value.diseaseResearchOutput}
          experimental
        />
        <Limitations values={limitations} />
      </div>
    </details>
  );
}

function ScanSummary({ data }: { data: UnknownRecord }) {
  return (
    <Ledger
      items={[
        displayLabel(data.protocol)
          ? { label: "Capture protocol", value: displayLabel(data.protocol)! }
          : null,
        displayLabel(data.status)
          ? { label: "Status", value: displayLabel(data.status)! }
          : null,
        date(data.createdAt)
          ? { label: "Created", value: date(data.createdAt)! }
          : null,
        date(data.updatedAt)
          ? { label: "Last updated", value: date(data.updatedAt)! }
          : null,
        date(data.completedAt)
          ? { label: "Completed", value: date(data.completedAt)! }
          : null,
      ]}
    />
  );
}

function LesionSummary({ data }: { data: UnknownRecord }) {
  const observations = strings(data.confirmedObservationIds);
  return (
    <>
      <Ledger
        items={[
          string(data.label)
            ? { label: "Label", value: string(data.label)! }
            : null,
          displayLabel(data.region)
            ? { label: "Region", value: displayLabel(data.region)! }
            : null,
          displayLabel(data.anatomicalSite)
            ? {
                label: "Anatomical site",
                value: displayLabel(data.anatomicalSite)!,
              }
            : null,
          displayLabel(data.status)
            ? { label: "Status", value: displayLabel(data.status)! }
            : null,
          {
            label: "Confirmed observations",
            value: String(observations.length),
          },
          date(data.createdAt)
            ? { label: "Created", value: date(data.createdAt)! }
            : null,
          date(data.updatedAt)
            ? { label: "Last updated", value: date(data.updatedAt)! }
            : null,
        ]}
      />
      <p className="authorized-resource__note">
        Observation links in this timeline were confirmed by the record owner.
      </p>
    </>
  );
}

function AnalysisSummary({ data }: { data: UnknownRecord }) {
  const observations = records(data.observations);
  const reasons = strings(data.abstentionReasons);
  return (
    <>
      <Ledger
        items={[
          displayLabel(data.status)
            ? { label: "Analysis status", value: displayLabel(data.status)! }
            : null,
          displayLabel(data.inputOrigin)
            ? { label: "Input source", value: displayLabel(data.inputOrigin)! }
            : null,
          displayLabel(data.analysisOrigin)
            ? {
                label: "Analysis source",
                value: displayLabel(data.analysisOrigin)!,
              }
            : null,
          strings(data.requestedHeads).length
            ? {
                label: "Requested outputs",
                value: strings(data.requestedHeads)
                  .map(readableLabel)
                  .join(", "),
              }
            : null,
          {
            label: "Candidate observations",
            value: String(observations.length),
          },
          date(data.startedAt)
            ? { label: "Started", value: date(data.startedAt)! }
            : null,
          date(data.completedAt)
            ? { label: "Completed", value: date(data.completedAt)! }
            : null,
        ]}
      />
      {reasons.length ? (
        <div className="authorized-resource__limitations">
          <h3>Why analysis did not complete</h3>
          <ul>
            {reasons.map((reason, index) => (
              <li key={`${index}:${reason}`}>{reason}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {observations.length ? (
        <section
          className="authorized-resource__observations"
          aria-label="Candidate observations"
        >
          {observations.map((observation, index) => (
            <Observation
              key={string(observation.observationId) ?? String(index)}
              value={observation}
              index={index}
            />
          ))}
        </section>
      ) : null}
    </>
  );
}

function ReportSummary({
  data,
  contentHref,
  viewerHeadingLevel,
}: {
  data: UnknownRecord;
  contentHref?: string;
  viewerHeadingLevel: "h3" | "h4";
}) {
  const sourceScans = strings(data.scanSessionIds);
  const inputOrigins = strings(data.inputOrigins);
  const analysisOrigins = strings(data.analysisOrigins);
  const rawFormat = string(data.format);
  const format =
    rawFormat && REPORT_FORMATS.has(rawFormat)
      ? (rawFormat as
          "pdf" | "html" | "fhir_r4_bundle" | "summary_video" | "transcript")
      : null;
  return (
    <>
      <Ledger
        items={[
          format ? { label: "Format", value: readableLabel(format) } : null,
          { label: "Source scans", value: String(sourceScans.length) },
          fileSize(data.byteSize)
            ? { label: "File size", value: fileSize(data.byteSize)! }
            : null,
          typeof data.accessible === "boolean"
            ? {
                label: "Accessible output",
                value: data.accessible ? "Yes" : "No",
              }
            : null,
          string(data.locale)
            ? { label: "Locale", value: string(data.locale)! }
            : null,
          inputOrigins.length
            ? {
                label: "Input source",
                value: inputOrigins.map(readableLabel).join(", "),
              }
            : null,
          analysisOrigins.length
            ? {
                label: "Analysis source",
                value: analysisOrigins.map(readableLabel).join(", "),
              }
            : null,
          date(data.createdAt)
            ? { label: "Prepared", value: date(data.createdAt)! }
            : null,
        ]}
      />
      {contentHref && format ? (
        <ReportFileViewer
          reportId={string(data.reportArtifactId) ?? undefined}
          contentHref={contentHref}
          format={format}
          headingLevel={viewerHeadingLevel}
          showDisclaimer={false}
        />
      ) : null}
    </>
  );
}

export function AuthorizedResourceView({
  resource,
  reportContentHref,
  headingLevel = "h2",
}: {
  resource: ResourceView;
  reportContentHref?: string;
  headingLevel?: "h2" | "h3";
}) {
  const data = resource.data;
  const Heading = headingLevel;
  return (
    <article className="authorized-resource">
      <header>
        <div>
          <p className="workspace-kicker">Authorized record</p>
          <Heading>{readableLabel(resource.resourceType)}</Heading>
        </div>
        <span>View only</span>
      </header>
      <p className="authorized-resource__id">{resource.resourceId}</p>
      {resource.resourceType === "scan_session" ? (
        <ScanSummary data={data} />
      ) : null}
      {resource.resourceType === "report" ? (
        <ReportSummary
          data={data}
          contentHref={reportContentHref}
          viewerHeadingLevel={headingLevel === "h2" ? "h3" : "h4"}
        />
      ) : null}
      {resource.resourceType === "lesion" ? (
        <LesionSummary data={data} />
      ) : null}
      {resource.resourceType === "analysis_run" ? (
        <AnalysisSummary data={data} />
      ) : null}
      <p className="record-disclaimer">{resource.disclaimer}</p>
    </article>
  );
}
