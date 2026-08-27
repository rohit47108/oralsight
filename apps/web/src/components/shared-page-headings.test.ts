import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ShareExchange } from "./share-exchange";
import { WorkspaceState } from "./workspace-state";

describe("shared page headings", () => {
  it("can render a standalone empty state with a page heading", () => {
    const markup = renderToStaticMarkup(
      createElement(WorkspaceState, {
        title: "No shared record was opened.",
        body: "Use the complete link supplied by the record owner.",
        headingLevel: "h1",
      }),
    );

    expect(markup).toContain("<h1>No shared record was opened.</h1>");
  });

  it("uses a page heading while a shared link is opening", () => {
    const markup = renderToStaticMarkup(
      createElement(ShareExchange, { shareId: "share-test" }),
    );

    expect(markup).toContain("<h1>Opening the shared record…</h1>");
  });
});
