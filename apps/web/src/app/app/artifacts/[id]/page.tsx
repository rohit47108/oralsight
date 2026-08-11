import type { Metadata } from "next";
import Link from "next/link";

import { ArtifactViewer } from "@/components/artifact-viewer";
import { WorkspaceState } from "@/components/workspace-state";
import { getGeneratedArtifact, PlatformApiError } from "@/lib/platform-api";
import { compactHash, readableDate, readableLabel } from "@/lib/presentation";

export const metadata: Metadata = { title: "Generated output" };

export default async function ArtifactPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const result = await getGeneratedArtifact(id).then(
    (artifact) => ({ ok: true as const, artifact }),
    (error: unknown) => ({ ok: false as const, error }),
  );
  if (!result.ok) {
    return (
      <div className="workspace-page">
        <WorkspaceState
          title="Generated output unavailable"
          body={
            result.error instanceof PlatformApiError
              ? result.error.message
              : "This output could not be opened."
          }
          action={{ href: "/app/reports", label: "Back to reports" }}
        />
      </div>
    );
  }
  const artifact = result.artifact;
  const contentHref = `/api/artifacts/${encodeURIComponent(artifact.artifactId)}/content`;
  return (
    <div className="workspace-page">
      <nav className="workspace-breadcrumb" aria-label="Breadcrumb">
        <Link href="/app/reports">Reports and media</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{readableLabel(artifact.purpose)}</span>
      </nav>
      <header className="record-heading">
        <div>
          <p className="workspace-kicker">Protected generated file</p>
          <h1>{artifact.filename}</h1>
          <p>Prepared {readableDate(artifact.createdAt)}</p>
        </div>
        <span className="record-status">Available</span>
      </header>
      <dl className="record-ledger">
        <div>
          <dt>Output ID</dt>
          <dd>{artifact.artifactId}</dd>
        </div>
        <div>
          <dt>Generation job</dt>
          <dd>{artifact.jobId}</dd>
        </div>
        <div>
          <dt>File size</dt>
          <dd>{(artifact.sizeBytes / 1024 / 1024).toFixed(2)} MB</dd>
        </div>
        <div>
          <dt>Retention ends</dt>
          <dd>{readableDate(artifact.retentionExpiresAt)}</dd>
        </div>
        <div>
          <dt>Content hash</dt>
          <dd title={artifact.sha256}>{compactHash(artifact.sha256)}</dd>
        </div>
        <div>
          <dt>File type</dt>
          <dd>{artifact.mediaType}</dd>
        </div>
      </dl>
      <ArtifactViewer
        artifactId={artifact.artifactId}
        filename={artifact.filename}
        mediaType={artifact.mediaType}
        purpose={artifact.purpose}
        contentHref={contentHref}
        manifest={artifact.manifest}
      />
    </div>
  );
}
