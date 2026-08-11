"use client";

export function PrintButton() {
  return (
    <button
      className="button print-button"
      type="button"
      onClick={() => window.print()}
    >
      Print calibration card
    </button>
  );
}
