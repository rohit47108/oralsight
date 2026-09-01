export function PhoneCapture() {
  return (
    <div
      className="phone-scene"
      role="img"
      aria-label="Stoma3D capture screen preview showing the third of eight regions"
    >
      <div className="phone-scene__halo" aria-hidden="true" />
      <div className="phone">
        <div className="phone__speaker" aria-hidden="true" />
        <div className="phone__screen">
          <div className="phone__topline">
            <span aria-hidden="true">×</span>
            <strong>Capture</strong>
            <span className="phone__help" aria-hidden="true">
              ?
            </span>
          </div>
          <div className="phone__step">
            <strong>Inside left cheek</strong>
            <span>3 of 8</span>
          </div>
          <div className="capture-window" aria-hidden="true">
            <span className="capture-corner capture-corner--one" />
            <span className="capture-corner capture-corner--two" />
            <span className="capture-corner capture-corner--three" />
            <span className="capture-corner capture-corner--four" />
            <svg viewBox="0 0 210 180">
              <path d="M28 113c17-63 54-92 108-77 28 8 47 27 54 55-33 7-58 29-75 66-38 2-67-13-87-44Z" />
              <path d="M54 114c22-37 55-52 99-45M92 153c13-27 35-46 67-56" />
              <circle cx="110" cy="92" r="26" />
            </svg>
            <span className="capture-window__label">Live camera area</span>
          </div>
          <p className="phone__instruction">
            Hold still and keep the whole area in frame.
          </p>
          <div className="phone__quality">
            <span className="quality-dot" />
            Light and focus look ready
          </div>
          <div className="phone__controls" aria-hidden="true">
            <span>Light</span>
            <i />
            <span>Flip</span>
          </div>
        </div>
      </div>
    </div>
  );
}
