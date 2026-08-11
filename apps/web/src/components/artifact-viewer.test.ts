import { describe, expect, it } from "vitest";

import { artifactViewerTesting } from "@/components/artifact-viewer";

function pad4(value: Uint8Array, byte: number): Uint8Array {
  const output = new Uint8Array(Math.ceil(value.length / 4) * 4);
  output.fill(byte);
  output.set(value);
  return output;
}

type SurfaceOptions = {
  colorAccessor?: Partial<{
    componentType: number;
    count: number;
    type: string;
  }>;
  colors?: Float32Array;
  includeColor?: boolean;
};

function minimalSurface(options: SurfaceOptions = {}): ArrayBuffer {
  const includeColor = options.includeColor ?? true;
  const positions = new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]);
  const normals = new Float32Array([0, 0, 1, 0, 0, 1, 0, 0, 1]);
  const colors =
    options.colors ??
    new Float32Array([1, 0.5, 0.25, 0.2, 0.4, 0.6, 0.9, 0.8, 0.7]);
  const indices = new Uint16Array([0, 1, 2]);
  const colorOffset = positions.byteLength + normals.byteLength;
  const indexOffset = colorOffset + (includeColor ? colors.byteLength : 0);
  const rawLength = indexOffset + indices.byteLength;
  const binary = new Uint8Array(Math.ceil(rawLength / 4) * 4);
  binary.set(new Uint8Array(positions.buffer), 0);
  binary.set(new Uint8Array(normals.buffer), positions.byteLength);
  if (includeColor) binary.set(new Uint8Array(colors.buffer), colorOffset);
  binary.set(new Uint8Array(indices.buffer), indexOffset);

  const bufferViews = [
    { buffer: 0, byteOffset: 0, byteLength: positions.byteLength },
    {
      buffer: 0,
      byteOffset: positions.byteLength,
      byteLength: normals.byteLength,
    },
  ];
  const accessors: Array<Record<string, unknown>> = [
    { bufferView: 0, componentType: 5126, count: 3, type: "VEC3" },
    { bufferView: 1, componentType: 5126, count: 3, type: "VEC3" },
  ];
  let indexAccessor = 2;
  const attributes: Record<string, number> = { POSITION: 0, NORMAL: 1 };
  if (includeColor) {
    bufferViews.push({
      buffer: 0,
      byteOffset: colorOffset,
      byteLength: colors.byteLength,
    });
    accessors.push({
      bufferView: 2,
      componentType: options.colorAccessor?.componentType ?? 5126,
      count: options.colorAccessor?.count ?? 3,
      type: options.colorAccessor?.type ?? "VEC3",
    });
    attributes.COLOR_0 = 2;
    indexAccessor = 3;
  }
  bufferViews.push({
    buffer: 0,
    byteOffset: indexOffset,
    byteLength: indices.byteLength,
  });
  accessors.push({
    bufferView: indexAccessor,
    componentType: 5123,
    count: 3,
    type: "SCALAR",
  });

  const document = {
    asset: { version: "2.0" },
    scene: 0,
    scenes: [{ nodes: [0] }],
    nodes: [{ mesh: 0, translation: [2, 3, 4] }],
    meshes: [
      {
        primitives: [
          {
            attributes,
            indices: indexAccessor,
            material: 0,
          },
        ],
      },
    ],
    materials: [
      { pbrMetallicRoughness: { baseColorFactor: [0.1, 0.2, 0.3, 1] } },
    ],
    buffers: [{ byteLength: binary.byteLength }],
    bufferViews,
    accessors,
  };
  const json = pad4(new TextEncoder().encode(JSON.stringify(document)), 0x20);
  const totalLength = 12 + 8 + json.length + 8 + binary.length;
  const output = new ArrayBuffer(totalLength);
  const view = new DataView(output);
  view.setUint32(0, 0x46546c67, true);
  view.setUint32(4, 2, true);
  view.setUint32(8, totalLength, true);
  view.setUint32(12, json.length, true);
  view.setUint32(16, 0x4e4f534a, true);
  new Uint8Array(output, 20, json.length).set(json);
  const binaryHeader = 20 + json.length;
  view.setUint32(binaryHeader, binary.length, true);
  view.setUint32(binaryHeader + 4, 0x004e4942, true);
  new Uint8Array(output, binaryHeader + 8, binary.length).set(binary);
  return output;
}

describe("GLB observation-surface boundary", () => {
  it("reads geometry, placement, material color, and FLOAT VEC3 vertex color", () => {
    const [mesh] = artifactViewerTesting.parseGlb(minimalSurface());
    expect(mesh.indices).toEqual(new Uint32Array([0, 1, 2]));
    expect(Array.from(mesh.positions.slice(0, 3))).toEqual([2, 3, 4]);
    expect(mesh.baseColorFactor).toEqual([0.1, 0.2, 0.3, 1]);
    expect(Array.from(mesh.vertexColors.slice(0, 3))).toEqual([1, 0.5, 0.25]);
  });

  it("uses constant white vertex color when COLOR_0 is absent", () => {
    const [mesh] = artifactViewerTesting.parseGlb(
      minimalSurface({ includeColor: false }),
    );
    expect(Array.from(mesh.vertexColors)).toEqual([1, 1, 1, 1, 1, 1, 1, 1, 1]);
    expect(mesh.baseColorFactor).toEqual([0.1, 0.2, 0.3, 1]);
  });

  it("rejects a COLOR_0 accessor that is not FLOAT VEC3", () => {
    expect(() =>
      artifactViewerTesting.parseGlb(
        minimalSurface({ colorAccessor: { componentType: 5123 } }),
      ),
    ).toThrow("unsupported geometry");
    expect(() =>
      artifactViewerTesting.parseGlb(
        minimalSurface({ colorAccessor: { type: "VEC4" } }),
      ),
    ).toThrow("unsupported geometry");
  });

  it("rejects out-of-range projected color values", () => {
    expect(() =>
      artifactViewerTesting.parseGlb(
        minimalSurface({
          colors: new Float32Array([
            1.2, 0.5, 0.25, 0.2, 0.4, 0.6, 0.9, 0.8, 0.7,
          ]),
        }),
      ),
    ).toThrow("invalid vertex color");
  });

  it("rejects bytes that are not a version-two GLB", () => {
    expect(() =>
      artifactViewerTesting.parseGlb(new Uint8Array(24).buffer),
    ).toThrow("could not be verified");
  });

  it("keeps lighting correct under non-uniform mesh scale", () => {
    const transformed = artifactViewerTesting.transformNormal(
      [2, 0, 0, 0, 0, 3, 0, 0, 0, 0, 4, 0, 0, 0, 0, 1],
      1,
      1,
      0,
    );
    expect(transformed[0]).toBeCloseTo(0.83205, 4);
    expect(transformed[1]).toBeCloseTo(0.5547, 4);
    expect(transformed[2]).toBeCloseTo(0, 4);
  });
});
