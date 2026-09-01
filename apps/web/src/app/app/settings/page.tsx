import type { Metadata } from "next";

import { AnalyticsConsentForm } from "@/components/analytics-consent-form";
import { DeleteAccountForm } from "@/components/delete-account-form";
import { WorkspaceState } from "@/components/workspace-state";
import { getProductContext } from "@/lib/product-auth";
import { getAnalyticsConsent } from "@/lib/platform-api";
import { readableDate } from "@/lib/presentation";

export const metadata: Metadata = { title: "Account" };

export default async function AccountPage() {
  const context = await getProductContext();
  if (context.state !== "ready") return null;
  const analytics = await getAnalyticsConsent().then(
    (value) => ({ ok: true as const, value }),
    () => ({ ok: false as const }),
  );
  return (
    <div className="workspace-page">
      <header className="workspace-heading">
        <div>
          <p className="workspace-kicker">Account</p>
          <h1>Identity, access, and deletion.</h1>
          <p>
            Sign-in information stays with the identity provider. Stoma3D
            account records stay in the platform service.
          </p>
        </div>
      </header>
      <section className="settings-ledger" aria-labelledby="identity-title">
        <div>
          <p className="workspace-kicker">Signed in</p>
          <h2 id="identity-title">Account identity</h2>
        </div>
        <dl>
          <div>
            <dt>Name</dt>
            <dd>{context.identity.displayName}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{context.identity.email ?? "Not provided"}</dd>
          </div>
          <div>
            <dt>Platform role</dt>
            <dd>Patient</dd>
          </div>
          <div>
            <dt>Account created</dt>
            <dd>{readableDate(context.account.createdAt)}</dd>
          </div>
        </dl>
      </section>
      <section className="settings-section" aria-labelledby="analytics-title">
        <div>
          <p className="workspace-kicker">Privacy choice</p>
          <h2 id="analytics-title">Product analytics</h2>
          <p>
            You decide whether Stoma3D may collect a short-lived record of basic
            app use. This setting does not affect scans, analysis, or sharing.
          </p>
        </div>
        {analytics.ok ? (
          <AnalyticsConsentForm
            initialEnabled={analytics.value.enabled}
            initialUpdatedAt={analytics.value.updatedAt}
          />
        ) : (
          <WorkspaceState
            title="This privacy setting could not be loaded."
            body="Analytics remain unchanged. Try again when the service is available."
          />
        )}
      </section>
      <section className="danger-zone" aria-labelledby="delete-title">
        <div>
          <p className="workspace-kicker">Permanent deletion</p>
          <h2 id="delete-title">Delete all Stoma3D account data</h2>
          <p>
            This queues removal of account rows, images, generated files, and
            reports. The request cannot be undone after deletion finishes.
          </p>
        </div>
        <DeleteAccountForm operationKey={crypto.randomUUID()} />
      </section>
    </div>
  );
}
