import { ImageResponse } from "next/og";

export const alt = "OralSight - A clearer way to keep track";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        color: "#142d31",
        background: "#f7faf8",
        fontFamily: "Arial, sans-serif",
      }}
    >
      <div
        style={{
          width: 310,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "58px 44px",
          color: "#ffffff",
          background: "#096d67",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            fontSize: 32,
            fontWeight: 700,
          }}
        >
          <span
            style={{
              width: 42,
              height: 42,
              border: "7px solid #ffffff",
              borderRadius: 42,
            }}
          />
          OralSight
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {["Consent", "Eight regions", "Review", "Share"].map(
            (step, index) => (
              <div
                key={step}
                style={{ display: "flex", alignItems: "center", gap: 13 }}
              >
                <span style={{ fontSize: 15, opacity: 0.72 }}>
                  0{index + 1}
                </span>
                <span style={{ fontSize: 21 }}>{step}</span>
              </div>
            ),
          )}
        </div>
      </div>
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "70px 84px",
        }}
      >
        <div
          style={{
            color: "#096d67",
            fontSize: 21,
            fontWeight: 700,
            marginBottom: 30,
          }}
        >
          A guided record, not a guess.
        </div>
        <div
          style={{
            maxWidth: 700,
            fontSize: 76,
            fontWeight: 760,
            lineHeight: 1.03,
            letterSpacing: "-3px",
          }}
        >
          A clearer way to keep track.
        </div>
        <div
          style={{
            maxWidth: 650,
            marginTop: 32,
            color: "#50666a",
            fontSize: 25,
            lineHeight: 1.45,
          }}
        >
          One consistent eight-region path for private, non-diagnostic oral
          observations.
        </div>
      </div>
    </div>,
    size,
  );
}
