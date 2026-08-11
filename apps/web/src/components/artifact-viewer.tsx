"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type ArtifactViewerProps = {
  artifactId: string;
  filename: string;
  mediaType: string;
  purpose: string;
  contentHref: string;
  manifest: Record<string, unknown>;
};

type ViewerState =
  | { status: "loading" }
  | { status: "ready"; meshCount: number }
  | { status: "error"; message: string };

type SurfaceMesh = {
  positions: Float32Array;
  normals: Float32Array;
  vertexColors: Float32Array;
  indices: Uint32Array;
  baseColorFactor: [number, number, number, number];
};

type GlbAccessor = {
  bufferView?: number;
  byteOffset?: number;
  componentType: number;
  count: number;
  normalized?: boolean;
  type: string;
};

type GlbDocument = {
  accessors?: GlbAccessor[];
  bufferViews?: Array<{
    buffer?: number;
    byteOffset?: number;
    byteLength: number;
    byteStride?: number;
  }>;
  materials?: Array<{
    pbrMetallicRoughness?: { baseColorFactor?: number[] };
  }>;
  meshes?: Array<{
    primitives?: Array<{
      attributes?: { POSITION?: number; NORMAL?: number; COLOR_0?: number };
      indices?: number;
      material?: number;
      mode?: number;
    }>;
  }>;
  nodes?: Array<{
    children?: number[];
    mesh?: number;
    matrix?: number[];
    rotation?: number[];
    scale?: number[];
    translation?: number[];
  }>;
  scene?: number;
  scenes?: Array<{ nodes?: number[] }>;
};

const GLB_MAGIC = 0x46546c67;
const GLB_JSON_CHUNK = 0x4e4f534a;
const GLB_BINARY_CHUNK = 0x004e4942;

function multiply4(left: number[], right: number[]): number[] {
  const output = new Array<number>(16).fill(0);
  for (let column = 0; column < 4; column += 1) {
    for (let row = 0; row < 4; row += 1) {
      for (let inner = 0; inner < 4; inner += 1) {
        output[column * 4 + row] +=
          left[inner * 4 + row] * right[column * 4 + inner];
      }
    }
  }
  return output;
}

function nodeMatrix(node: NonNullable<GlbDocument["nodes"]>[number]): number[] {
  if (node.matrix?.length === 16) return node.matrix;
  const [x = 0, y = 0, z = 0, w = 1] = node.rotation ?? [];
  const [sx = 1, sy = 1, sz = 1] = node.scale ?? [];
  const [tx = 0, ty = 0, tz = 0] = node.translation ?? [];
  const x2 = x + x;
  const y2 = y + y;
  const z2 = z + z;
  const xx = x * x2;
  const xy = x * y2;
  const xz = x * z2;
  const yy = y * y2;
  const yz = y * z2;
  const zz = z * z2;
  const wx = w * x2;
  const wy = w * y2;
  const wz = w * z2;
  return [
    (1 - (yy + zz)) * sx,
    (xy + wz) * sx,
    (xz - wy) * sx,
    0,
    (xy - wz) * sy,
    (1 - (xx + zz)) * sy,
    (yz + wx) * sy,
    0,
    (xz + wy) * sz,
    (yz - wx) * sz,
    (1 - (xx + yy)) * sz,
    0,
    tx,
    ty,
    tz,
    1,
  ];
}

function transformPosition(matrix: number[], x: number, y: number, z: number) {
  return [
    matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12],
    matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13],
    matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14],
  ];
}

function transformNormal(matrix: number[], x: number, y: number, z: number) {
  const a00 = matrix[0];
  const a01 = matrix[4];
  const a02 = matrix[8];
  const a10 = matrix[1];
  const a11 = matrix[5];
  const a12 = matrix[9];
  const a20 = matrix[2];
  const a21 = matrix[6];
  const a22 = matrix[10];
  const c00 = a11 * a22 - a12 * a21;
  const c01 = a12 * a20 - a10 * a22;
  const c02 = a10 * a21 - a11 * a20;
  const c10 = a02 * a21 - a01 * a22;
  const c11 = a00 * a22 - a02 * a20;
  const c12 = a01 * a20 - a00 * a21;
  const c20 = a01 * a12 - a02 * a11;
  const c21 = a02 * a10 - a00 * a12;
  const c22 = a00 * a11 - a01 * a10;
  const determinant = a00 * c00 + a01 * c01 + a02 * c02;
  if (Math.abs(determinant) < 1e-12) return [0, 0, 1];
  const transformed = [
    (c00 * x + c01 * y + c02 * z) / determinant,
    (c10 * x + c11 * y + c12 * z) / determinant,
    (c20 * x + c21 * y + c22 * z) / determinant,
  ];
  const length = Math.hypot(...transformed) || 1;
  return transformed.map((value) => value / length);
}

function componentInfo(componentType: number) {
  switch (componentType) {
    case 5121:
      return {
        bytes: 1,
        read: (view: DataView, offset: number) => view.getUint8(offset),
      };
    case 5123:
      return {
        bytes: 2,
        read: (view: DataView, offset: number) => view.getUint16(offset, true),
      };
    case 5125:
      return {
        bytes: 4,
        read: (view: DataView, offset: number) => view.getUint32(offset, true),
      };
    case 5126:
      return {
        bytes: 4,
        read: (view: DataView, offset: number) => view.getFloat32(offset, true),
      };
    default:
      throw new Error(
        "This observation surface uses an unsupported data format.",
      );
  }
}

function componentCount(type: string): number {
  const counts: Record<string, number> = {
    SCALAR: 1,
    VEC2: 2,
    VEC3: 3,
    VEC4: 4,
    MAT4: 16,
  };
  const count = counts[type];
  if (!count)
    throw new Error("This observation surface has unsupported geometry.");
  return count;
}

function readAccessor(
  document: GlbDocument,
  binary: ArrayBuffer,
  accessorIndex: number,
): number[] {
  const accessor = document.accessors?.[accessorIndex];
  if (
    !accessor ||
    accessor.bufferView === undefined ||
    !Number.isInteger(accessor.count) ||
    accessor.count < 1
  ) {
    throw new Error("This observation surface is missing geometry.");
  }
  const bufferView = document.bufferViews?.[accessor.bufferView];
  if (
    !bufferView ||
    (bufferView.buffer ?? 0) !== 0 ||
    !Number.isInteger(bufferView.byteLength) ||
    bufferView.byteLength < 1
  ) {
    throw new Error("This observation surface is incomplete.");
  }
  const components = componentCount(accessor.type);
  const info = componentInfo(accessor.componentType);
  const elementBytes = components * info.bytes;
  const stride = bufferView.byteStride ?? elementBytes;
  const viewStart = bufferView.byteOffset ?? 0;
  const accessorOffset = accessor.byteOffset ?? 0;
  const start = viewStart + accessorOffset;
  const lastByte = start + (accessor.count - 1) * stride + elementBytes;
  if (
    !Number.isInteger(stride) ||
    stride < elementBytes ||
    !Number.isInteger(viewStart) ||
    viewStart < 0 ||
    !Number.isInteger(accessorOffset) ||
    accessorOffset < 0 ||
    lastByte > binary.byteLength ||
    lastByte > viewStart + bufferView.byteLength
  ) {
    throw new Error("This observation surface is incomplete.");
  }
  const view = new DataView(binary);
  const output = new Array<number>(accessor.count * components);
  for (let item = 0; item < accessor.count; item += 1) {
    for (let component = 0; component < components; component += 1) {
      output[item * components + component] = info.read(
        view,
        start + item * stride + component * info.bytes,
      );
    }
  }
  return output;
}

function requireAccessor(
  document: GlbDocument,
  accessorIndex: number,
  options: {
    componentTypes: readonly number[];
    count?: number;
    type: string;
  },
) {
  const accessor = document.accessors?.[accessorIndex];
  if (
    !accessor ||
    accessor.type !== options.type ||
    !options.componentTypes.includes(accessor.componentType) ||
    (options.count !== undefined && accessor.count !== options.count) ||
    accessor.normalized === true
  ) {
    throw new Error("This observation surface has unsupported geometry.");
  }
  return accessor;
}

function requireFinite(values: number[]) {
  if (!values.every(Number.isFinite)) {
    throw new Error("This observation surface contains invalid geometry.");
  }
}

function parseGlb(payload: ArrayBuffer): SurfaceMesh[] {
  const view = new DataView(payload);
  if (
    payload.byteLength < 20 ||
    view.getUint32(0, true) !== GLB_MAGIC ||
    view.getUint32(4, true) !== 2 ||
    view.getUint32(8, true) !== payload.byteLength
  ) {
    throw new Error("The observation surface file could not be verified.");
  }
  let cursor = 12;
  let document: GlbDocument | null = null;
  let binary: ArrayBuffer | null = null;
  while (cursor + 8 <= payload.byteLength) {
    const length = view.getUint32(cursor, true);
    const type = view.getUint32(cursor + 4, true);
    const start = cursor + 8;
    const end = start + length;
    if (end > payload.byteLength)
      throw new Error("The observation surface is incomplete.");
    if (type === GLB_JSON_CHUNK) {
      const json = new TextDecoder()
        .decode(payload.slice(start, end))
        .trimEnd();
      document = JSON.parse(json) as GlbDocument;
    } else if (type === GLB_BINARY_CHUNK) {
      binary = payload.slice(start, end);
    }
    cursor = end;
  }
  if (!document || !binary)
    throw new Error("The observation surface is incomplete.");
  const scene = document.scenes?.[document.scene ?? 0];
  const rootNodes =
    scene?.nodes ?? document.nodes?.map((_node, index) => index) ?? [];
  const meshes: SurfaceMesh[] = [];

  function visit(nodeIndex: number, parent: number[]) {
    const node = document?.nodes?.[nodeIndex];
    if (!node || !document || !binary) return;
    const transform = multiply4(parent, nodeMatrix(node));
    const mesh =
      node.mesh === undefined ? undefined : document.meshes?.[node.mesh];
    for (const primitive of mesh?.primitives ?? []) {
      if (primitive.mode !== undefined && primitive.mode !== 4) continue;
      const positionIndex = primitive.attributes?.POSITION;
      if (positionIndex === undefined) continue;
      const positionAccessor = requireAccessor(document, positionIndex, {
        componentTypes: [5126],
        type: "VEC3",
      });
      const positions = readAccessor(document, binary, positionIndex);
      requireFinite(positions);
      const normalIndex = primitive.attributes?.NORMAL;
      const sourceNormals =
        normalIndex === undefined
          ? null
          : (() => {
              requireAccessor(document, normalIndex, {
                componentTypes: [5126],
                count: positionAccessor.count,
                type: "VEC3",
              });
              const values = readAccessor(document, binary, normalIndex);
              requireFinite(values);
              return values;
            })();
      const colorIndex = primitive.attributes?.COLOR_0;
      const sourceColors =
        colorIndex === undefined
          ? null
          : (() => {
              requireAccessor(document, colorIndex, {
                componentTypes: [5126],
                count: positionAccessor.count,
                type: "VEC3",
              });
              const values = readAccessor(document, binary, colorIndex);
              if (
                !values.every(
                  (value) => Number.isFinite(value) && value >= 0 && value <= 1,
                )
              ) {
                throw new Error(
                  "This observation surface contains invalid vertex color data.",
                );
              }
              return values;
            })();
      if (primitive.indices !== undefined) {
        requireAccessor(document, primitive.indices, {
          componentTypes: [5121, 5123, 5125],
          type: "SCALAR",
        });
      }
      const indices =
        primitive.indices === undefined
          ? Array.from(
              { length: positions.length / 3 },
              (_value, index) => index,
            )
          : readAccessor(document, binary, primitive.indices);
      if (
        indices.length % 3 !== 0 ||
        !indices.every(
          (index) =>
            Number.isInteger(index) &&
            index >= 0 &&
            index < positionAccessor.count,
        )
      ) {
        throw new Error(
          "This observation surface contains invalid triangle data.",
        );
      }
      const transformedPositions = new Float32Array(positions.length);
      const transformedNormals = new Float32Array(positions.length);
      for (let index = 0; index < positions.length; index += 3) {
        transformedPositions.set(
          transformPosition(
            transform,
            positions[index],
            positions[index + 1],
            positions[index + 2],
          ),
          index,
        );
        const normal = sourceNormals
          ? transformNormal(
              transform,
              sourceNormals[index],
              sourceNormals[index + 1],
              sourceNormals[index + 2],
            )
          : [0, 0, 1];
        transformedNormals.set(normal, index);
      }
      const baseColor =
        primitive.material === undefined
          ? undefined
          : document.materials?.[primitive.material]?.pbrMetallicRoughness
              ?.baseColorFactor;
      if (
        baseColor &&
        (baseColor.length !== 4 ||
          !baseColor.every(
            (value) => Number.isFinite(value) && value >= 0 && value <= 1,
          ))
      ) {
        throw new Error(
          "This observation surface contains invalid material data.",
        );
      }
      meshes.push({
        positions: transformedPositions,
        normals: transformedNormals,
        vertexColors: sourceColors
          ? Float32Array.from(sourceColors)
          : new Float32Array(positionAccessor.count * 3).fill(1),
        indices: Uint32Array.from(indices),
        baseColorFactor: [
          baseColor?.[0] ?? 0.53,
          baseColor?.[1] ?? 0.34,
          baseColor?.[2] ?? 0.36,
          baseColor?.[3] ?? 1,
        ],
      });
    }
    for (const child of node.children ?? []) visit(child, transform);
  }

  const identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
  for (const node of rootNodes) visit(node, identity);
  if (meshes.length === 0)
    throw new Error("No viewable surface was found in this file.");
  return meshes;
}

function perspective(fov: number, aspect: number, near: number, far: number) {
  const scale = 1 / Math.tan(fov / 2);
  const range = 1 / (near - far);
  return [
    scale / aspect,
    0,
    0,
    0,
    0,
    scale,
    0,
    0,
    0,
    0,
    (far + near) * range,
    -1,
    0,
    0,
    2 * far * near * range,
    0,
  ];
}

function normalize3(vector: number[]) {
  const length = Math.hypot(...vector) || 1;
  return vector.map((value) => value / length);
}

function cross3(left: number[], right: number[]) {
  return [
    left[1] * right[2] - left[2] * right[1],
    left[2] * right[0] - left[0] * right[2],
    left[0] * right[1] - left[1] * right[0],
  ];
}

function lookAt(eye: number[], center: number[]) {
  const forward = normalize3(eye.map((value, index) => value - center[index]));
  const right = normalize3(cross3([0, 1, 0], forward));
  const up = cross3(forward, right);
  return [
    right[0],
    up[0],
    forward[0],
    0,
    right[1],
    up[1],
    forward[1],
    0,
    right[2],
    up[2],
    forward[2],
    0,
    -right.reduce((sum, value, index) => sum + value * eye[index], 0),
    -up.reduce((sum, value, index) => sum + value * eye[index], 0),
    -forward.reduce((sum, value, index) => sum + value * eye[index], 0),
    1,
  ];
}

function compileShader(
  gl: WebGL2RenderingContext,
  type: number,
  source: string,
) {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("WebGL could not create a shader.");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    gl.deleteShader(shader);
    throw new Error("WebGL could not prepare the observation surface.");
  }
  return shader;
}

function createProgram(gl: WebGL2RenderingContext) {
  const vertex = compileShader(
    gl,
    gl.VERTEX_SHADER,
    `#version 300 es
    precision highp float;
    in vec3 a_position;
    in vec3 a_normal;
    in vec3 a_vertex_color;
    uniform mat4 u_view_projection;
    out vec3 v_normal;
    out vec3 v_vertex_color;
    void main() {
      gl_Position = u_view_projection * vec4(a_position, 1.0);
      v_normal = a_normal;
      v_vertex_color = a_vertex_color;
    }`,
  );
  const fragment = compileShader(
    gl,
    gl.FRAGMENT_SHADER,
    `#version 300 es
    precision highp float;
    in vec3 v_normal;
    in vec3 v_vertex_color;
    uniform vec4 u_base_color;
    out vec4 out_color;
    void main() {
      vec3 normal = normalize(v_normal);
      float diffuse = max(dot(normal, normalize(vec3(-0.35, 0.8, 0.55))), 0.0);
      float light = 0.52 + diffuse * 0.48;
      out_color = vec4(v_vertex_color * u_base_color.rgb * light, u_base_color.a);
    }`,
  );
  const program = gl.createProgram();
  if (!program) throw new Error("WebGL could not create a program.");
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    gl.deleteProgram(program);
    throw new Error("WebGL could not prepare the observation surface.");
  }
  return program;
}

function GlbSurface({
  contentHref,
  filename,
}: {
  contentHref: string;
  filename: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const renderRef = useRef<
    ((view: { yaw: number; pitch: number; distance: number }) => void) | null
  >(null);
  const viewRef = useRef({ yaw: -0.35, pitch: 0.22, distance: 4.4 });
  const dragRef = useRef<{ id: number; x: number; y: number } | null>(null);
  const [state, setState] = useState<ViewerState>({ status: "loading" });

  const redraw = useCallback(() => renderRef.current?.(viewRef.current), []);
  const setView = useCallback(
    (next: Partial<typeof viewRef.current>) => {
      viewRef.current = { ...viewRef.current, ...next };
      redraw();
    },
    [redraw],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const surfaceCanvas = canvas;
    const controller = new AbortController();
    let cleanupRenderer = () => {};
    async function prepare() {
      try {
        const response = await fetch(contentHref, {
          cache: "no-store",
          credentials: "same-origin",
          signal: controller.signal,
        });
        if (!response.ok)
          throw new Error("The observation surface could not be downloaded.");
        const meshes = parseGlb(await response.arrayBuffer());
        if (controller.signal.aborted) return;
        const gl = surfaceCanvas.getContext("webgl2", {
          alpha: false,
          antialias: true,
          powerPreference: "high-performance",
        });
        if (!gl)
          throw new Error(
            "This browser cannot display the 3D observation surface.",
          );
        const program = createProgram(gl);
        const positionLocation = gl.getAttribLocation(program, "a_position");
        const normalLocation = gl.getAttribLocation(program, "a_normal");
        const vertexColorLocation = gl.getAttribLocation(
          program,
          "a_vertex_color",
        );
        const matrixLocation = gl.getUniformLocation(
          program,
          "u_view_projection",
        );
        const baseColorLocation = gl.getUniformLocation(
          program,
          "u_base_color",
        );
        const resources = meshes.map((mesh) => {
          const vertexArray = gl.createVertexArray();
          const positionBuffer = gl.createBuffer();
          const normalBuffer = gl.createBuffer();
          const vertexColorBuffer = gl.createBuffer();
          const indexBuffer = gl.createBuffer();
          if (
            !vertexArray ||
            !positionBuffer ||
            !normalBuffer ||
            !vertexColorBuffer ||
            !indexBuffer
          ) {
            throw new Error("WebGL ran out of resources.");
          }
          gl.bindVertexArray(vertexArray);
          gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, mesh.positions, gl.STATIC_DRAW);
          gl.enableVertexAttribArray(positionLocation);
          gl.vertexAttribPointer(positionLocation, 3, gl.FLOAT, false, 0, 0);
          gl.bindBuffer(gl.ARRAY_BUFFER, normalBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, mesh.normals, gl.STATIC_DRAW);
          gl.enableVertexAttribArray(normalLocation);
          gl.vertexAttribPointer(normalLocation, 3, gl.FLOAT, false, 0, 0);
          gl.bindBuffer(gl.ARRAY_BUFFER, vertexColorBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, mesh.vertexColors, gl.STATIC_DRAW);
          gl.enableVertexAttribArray(vertexColorLocation);
          gl.vertexAttribPointer(vertexColorLocation, 3, gl.FLOAT, false, 0, 0);
          gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indexBuffer);
          gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, mesh.indices, gl.STATIC_DRAW);
          return {
            vertexArray,
            positionBuffer,
            normalBuffer,
            vertexColorBuffer,
            indexBuffer,
            mesh,
          };
        });

        gl.enable(gl.DEPTH_TEST);
        gl.enable(gl.CULL_FACE);
        gl.cullFace(gl.BACK);
        const colorScheme = window.matchMedia("(prefers-color-scheme: dark)");
        const setClearColor = () => {
          if (colorScheme.matches) gl.clearColor(0.027, 0.09, 0.098, 1);
          else gl.clearColor(0.955, 0.973, 0.965, 1);
        };
        setClearColor();
        gl.useProgram(program);

        const render = (camera: {
          yaw: number;
          pitch: number;
          distance: number;
        }) => {
          const ratio = Math.min(window.devicePixelRatio || 1, 2);
          const width = Math.max(
            1,
            Math.floor(surfaceCanvas.clientWidth * ratio),
          );
          const height = Math.max(
            1,
            Math.floor(surfaceCanvas.clientHeight * ratio),
          );
          if (
            surfaceCanvas.width !== width ||
            surfaceCanvas.height !== height
          ) {
            surfaceCanvas.width = width;
            surfaceCanvas.height = height;
          }
          gl.viewport(0, 0, width, height);
          gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
          const eye = [
            Math.sin(camera.yaw) * Math.cos(camera.pitch) * camera.distance,
            Math.sin(camera.pitch) * camera.distance,
            Math.cos(camera.yaw) * Math.cos(camera.pitch) * camera.distance,
          ];
          const projection = perspective(Math.PI / 4, width / height, 0.05, 50);
          gl.uniformMatrix4fv(
            matrixLocation,
            false,
            new Float32Array(multiply4(projection, lookAt(eye, [0, -0.1, 0]))),
          );
          for (const resource of resources) {
            gl.bindVertexArray(resource.vertexArray);
            gl.uniform4fv(baseColorLocation, resource.mesh.baseColorFactor);
            gl.drawElements(
              gl.TRIANGLES,
              resource.mesh.indices.length,
              gl.UNSIGNED_INT,
              0,
            );
          }
        };
        renderRef.current = render;
        const resize = new ResizeObserver(redraw);
        resize.observe(surfaceCanvas);
        const handleColorScheme = () => {
          setClearColor();
          render(viewRef.current);
        };
        colorScheme.addEventListener("change", handleColorScheme);
        cleanupRenderer = () => {
          resize.disconnect();
          colorScheme.removeEventListener("change", handleColorScheme);
          renderRef.current = null;
          for (const resource of resources) {
            gl.deleteVertexArray(resource.vertexArray);
            gl.deleteBuffer(resource.positionBuffer);
            gl.deleteBuffer(resource.normalBuffer);
            gl.deleteBuffer(resource.vertexColorBuffer);
            gl.deleteBuffer(resource.indexBuffer);
          }
          gl.deleteProgram(program);
        };
        setState({ status: "ready", meshCount: meshes.length });
        render(viewRef.current);
      } catch (error) {
        if (controller.signal.aborted) return;
        setState({
          status: "error",
          message:
            error instanceof Error
              ? error.message
              : "The observation surface could not be displayed.",
        });
      }
    }
    void prepare();
    return () => {
      controller.abort();
      cleanupRenderer();
    };
  }, [contentHref, redraw]);

  return (
    <div className="glb-viewer" data-state={state.status}>
      <canvas
        ref={canvasRef}
        tabIndex={0}
        role="img"
        aria-label="Interactive oral observation surface. Drag to rotate, use the wheel or controls to zoom."
        onPointerDown={(event) => {
          event.currentTarget.setPointerCapture(event.pointerId);
          dragRef.current = {
            id: event.pointerId,
            x: event.clientX,
            y: event.clientY,
          };
        }}
        onPointerMove={(event) => {
          const drag = dragRef.current;
          if (!drag || drag.id !== event.pointerId) return;
          const dx = event.clientX - drag.x;
          const dy = event.clientY - drag.y;
          dragRef.current = { ...drag, x: event.clientX, y: event.clientY };
          setView({
            yaw: viewRef.current.yaw + dx * 0.008,
            pitch: Math.max(
              -1.15,
              Math.min(1.15, viewRef.current.pitch + dy * 0.008),
            ),
          });
        }}
        onPointerUp={(event) => {
          if (dragRef.current?.id === event.pointerId) dragRef.current = null;
        }}
        onPointerCancel={() => {
          dragRef.current = null;
        }}
        onWheel={(event) => {
          event.preventDefault();
          setView({
            distance: Math.max(
              2.4,
              Math.min(8, viewRef.current.distance + event.deltaY * 0.004),
            ),
          });
        }}
        onKeyDown={(event) => {
          const amount = event.shiftKey ? 0.25 : 0.1;
          if (event.key === "ArrowLeft")
            setView({ yaw: viewRef.current.yaw - amount });
          else if (event.key === "ArrowRight")
            setView({ yaw: viewRef.current.yaw + amount });
          else if (event.key === "ArrowUp")
            setView({ pitch: Math.max(-1.15, viewRef.current.pitch - amount) });
          else if (event.key === "ArrowDown")
            setView({ pitch: Math.min(1.15, viewRef.current.pitch + amount) });
          else return;
          event.preventDefault();
        }}
      />
      {state.status === "loading" ? (
        <div className="glb-viewer__status" role="status">
          <span className="workspace-spinner" aria-hidden="true" />
          <span>Preparing observation surface…</span>
        </div>
      ) : null}
      {state.status === "error" ? (
        <div className="glb-viewer__status" role="alert">
          <strong>3D preview unavailable</strong>
          <span>{state.message}</span>
        </div>
      ) : null}
      <div
        className="glb-viewer__controls"
        aria-label="Observation surface controls"
      >
        <button
          type="button"
          onClick={() =>
            setView({ distance: Math.max(2.4, viewRef.current.distance - 0.5) })
          }
          aria-label="Zoom in"
        >
          +
        </button>
        <button
          type="button"
          onClick={() =>
            setView({ distance: Math.min(8, viewRef.current.distance + 0.5) })
          }
          aria-label="Zoom out"
        >
          −
        </button>
        <button
          type="button"
          onClick={() => {
            viewRef.current = { yaw: -0.35, pitch: 0.22, distance: 4.4 };
            redraw();
          }}
        >
          Reset
        </button>
      </div>
      <a
        className="glb-viewer__download"
        href={contentHref}
        download={filename}
      >
        Download GLB
      </a>
    </div>
  );
}

function ManifestSummary({ manifest }: { manifest: Record<string, unknown> }) {
  const limitations = Array.isArray(manifest.limitations)
    ? manifest.limitations.filter(
        (item): item is string => typeof item === "string",
      )
    : [];
  const generatedAt =
    typeof manifest.generatedAt === "string" ? manifest.generatedAt : null;
  const schemaVersion =
    typeof manifest.schemaVersion === "string" ? manifest.schemaVersion : null;
  const personalization =
    manifest.personalization &&
    typeof manifest.personalization === "object" &&
    !Array.isArray(manifest.personalization)
      ? (manifest.personalization as Record<string, unknown>)
      : null;
  const projectionMethod =
    personalization?.method === "multi_view_vertex_color_projection"
      ? "Coarse color from accepted scan views"
      : null;
  const projectedRegionCount =
    typeof personalization?.projectedRegionCount === "number" &&
    Number.isInteger(personalization.projectedRegionCount) &&
    personalization.projectedRegionCount >= 0 &&
    personalization.projectedRegionCount <= 8
      ? personalization.projectedRegionCount
      : null;
  const standardGeometry = personalization?.changesAnatomicalGeometry === false;
  return (
    <div className="artifact-manifest">
      <dl>
        {generatedAt ? (
          <div>
            <dt>Generated</dt>
            <dd>{new Date(generatedAt).toLocaleString("en-US")}</dd>
          </div>
        ) : null}
        {schemaVersion ? (
          <div>
            <dt>Renderer record</dt>
            <dd>{schemaVersion}</dd>
          </div>
        ) : null}
        {projectionMethod ? (
          <div>
            <dt>Surface color</dt>
            <dd>{projectionMethod}</dd>
          </div>
        ) : null}
        {projectedRegionCount !== null ? (
          <div>
            <dt>Projected coverage</dt>
            <dd>{projectedRegionCount} of 8 regions</dd>
          </div>
        ) : null}
        {standardGeometry ? (
          <div>
            <dt>Shape</dt>
            <dd>Standard oral region map</dd>
          </div>
        ) : null}
      </dl>
      {limitations.length ? (
        <div>
          <h3>Important limits</h3>
          <ul>
            {limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export function ArtifactViewer({
  artifactId,
  filename,
  mediaType,
  purpose,
  contentHref,
  manifest,
}: ArtifactViewerProps) {
  return (
    <section
      className="artifact-player"
      aria-labelledby={`artifact-${artifactId}`}
    >
      <header>
        <div>
          <p className="workspace-kicker">Generated output</p>
          <h2 id={`artifact-${artifactId}`}>
            {purpose === "summary_video"
              ? "Scan summary video"
              : "Oral observation surface"}
          </h2>
        </div>
        <span>{mediaType === "video/mp4" ? "MP4" : "GLB"}</span>
      </header>
      {mediaType === "video/mp4" ? (
        <div className="summary-video-player">
          <video controls playsInline preload="metadata">
            <source src={contentHref} type="video/mp4" />
            Your browser cannot play this video. Use the download link below.
          </video>
          <a className="text-link" href={contentHref} download={filename}>
            Download video
          </a>
        </div>
      ) : mediaType === "model/gltf-binary" ? (
        <GlbSurface contentHref={contentHref} filename={filename} />
      ) : (
        <div className="artifact-unsupported">
          <p>This file type cannot be previewed here.</p>
          <a className="button" href={contentHref} download={filename}>
            Download file
          </a>
        </div>
      )}
      <ManifestSummary manifest={manifest} />
      <p className="record-disclaimer">This result is not a diagnosis.</p>
    </section>
  );
}

export const artifactViewerTesting = { parseGlb, transformNormal };
