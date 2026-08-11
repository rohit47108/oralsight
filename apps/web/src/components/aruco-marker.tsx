export const ARUCO_4X4_50_MARKER_17 = [
  "111111",
  "110011",
  "110011",
  "111111",
  "111111",
  "111111",
] as const;

export function ArucoMarker17() {
  return (
    <svg
      className="physical-scale-marker"
      viewBox="0 0 6 6"
      role="img"
      aria-label="ArUco dictionary 4 by 4 marker 17, twenty millimeters square"
      shapeRendering="crispEdges"
    >
      <rect width="6" height="6" fill="#fff" />
      {ARUCO_4X4_50_MARKER_17.flatMap((row, y) =>
        [...row].map((module, x) =>
          module === "1" ? (
            <rect
              key={`${x}:${y}`}
              x={x}
              y={y}
              width="1"
              height="1"
              fill="#000"
            />
          ) : null,
        ),
      )}
    </svg>
  );
}
