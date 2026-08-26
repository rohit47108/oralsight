import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ProductGate } from "@/components/product-gate";

describe("ProductGate landmarks", () => {
  it("uses the existing public-page main landmark when embedded", () => {
    const markup = renderToStaticMarkup(
      createElement(ProductGate, {
        context: { state: "signed_out" },
        returnTo: "/professional-apply",
        embeddedInSiteMain: true,
      }),
    );

    expect(markup).toContain('<div class="product-gate"');
    expect(markup).not.toContain("<main");
    expect(markup).not.toContain('id="main-content"');
  });

  it("keeps a main landmark on standalone product routes", () => {
    const markup = renderToStaticMarkup(
      createElement(ProductGate, { context: { state: "signed_out" } }),
    );

    expect(markup).toContain('<main class="product-gate" id="main-content"');
  });
});
