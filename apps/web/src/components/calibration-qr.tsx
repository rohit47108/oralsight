"use client";

import QRCode from "react-qr-code";

export const CALIBRATION_QR_PAYLOAD =
  '{"marker_dictionary":"DICT_4X4_50","marker_id":17,"marker_side_mm":20.0,"reference_bar_mm":50.0,"schema":"stoma3d_calibration_card","version":"stoma3d-calibration-v1"}';

export function CalibrationQr() {
  return (
    <div
      className="calibration-qr"
      aria-label="Calibration marker metadata QR code"
    >
      <QRCode value={CALIBRATION_QR_PAYLOAD} size={128} level="M" />
    </div>
  );
}
