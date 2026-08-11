import { mouthRegions } from "@/content/site";

const markers = [
  { x: 180, y: 277 },
  { x: 180, y: 335 },
  { x: 76, y: 189 },
  { x: 284, y: 189 },
  { x: 180, y: 80 },
  { x: 180, y: 376 },
  { x: 180, y: 132 },
  { x: 180, y: 230 },
] as const;

export function RegionMap({ compact = false }: { compact?: boolean }) {
  return (
    <figure
      className={compact ? "region-map region-map--compact" : "region-map"}
    >
      <svg
        className="region-map__drawing"
        viewBox="0 0 360 420"
        role="img"
        aria-labelledby="region-map-title region-map-description"
      >
        <title id="region-map-title">The eight OralSight capture regions</title>
        <desc id="region-map-description">
          A simplified front-facing mouth guide with numbered markers. The full
          text list follows the drawing.
        </desc>
        <path
          className="mouth-outline"
          d="M71 178C82 86 124 42 180 42s98 44 109 136c8 67-16 166-109 190C87 344 63 245 71 178Z"
        />
        <path
          className="mouth-detail"
          d="M101 153c20-41 49-61 79-61s59 20 79 61M99 229c18 79 48 108 81 108s63-29 81-108"
        />
        <path
          className="mouth-detail"
          d="M112 157c45-26 91-26 136 0-17 24-40 36-68 36s-51-12-68-36Z"
        />
        <path
          className="mouth-detail mouth-detail--fill"
          d="M127 251c15-31 33-47 53-47s38 16 53 47c-14 55-32 81-53 81s-39-26-53-81Z"
        />
        <path className="mouth-detail" d="M115 145h130M113 241h134" />
        <path
          className="mouth-faint"
          d="M132 122v48M156 111v68M180 107v78M204 111v68M228 122v48"
        />
        <path
          className="mouth-faint"
          d="M133 231v52M157 222v82M180 217v96M203 222v82M227 231v52"
        />
        {mouthRegions.map((region, index) => (
          <g
            className="region-marker"
            data-region={region.id}
            key={region.id}
            transform={`translate(${markers[index].x} ${markers[index].y})`}
          >
            <circle r="15" />
            <text textAnchor="middle" dominantBaseline="central">
              {region.number}
            </text>
          </g>
        ))}
      </svg>
      <figcaption>
        <p className="region-map__caption">
          One session. Eight consistent views.
        </p>
        <ol className="region-list" aria-label="Capture regions">
          {mouthRegions.map((region) => (
            <li key={region.id}>
              <span aria-hidden="true">{region.number}</span>
              {region.label}
            </li>
          ))}
        </ol>
      </figcaption>
    </figure>
  );
}
