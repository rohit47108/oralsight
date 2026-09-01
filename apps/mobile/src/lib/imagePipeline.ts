import { Skia } from "@shopify/react-native-skia";
import * as FileSystem from "expo-file-system/legacy";
import { manipulateAsync, SaveFormat } from "expo-image-manipulator";
import { Image as NativeImage } from "react-native";

import { TRANSPORT_IMAGE_BYTE_LIMIT } from "@/constants";
import { evaluateImageTelemetry, type ImageTelemetry } from "@/lib/quality";
import { createStoma3DTempUri, removeFileIfPresent } from "@/lib/tempFiles";

export interface SanitizedCapture {
  uri: string;
  mimeType: "image/jpeg" | "image/png";
  telemetry: ImageTelemetry;
  source: "camera" | "photo_library" | "video_sweep";
  width: number;
  height: number;
  byteSize: number;
}

// Vercel Functions reject a whole request above 4.5 MB. Two comparison images
// plus multipart metadata therefore need a deliberately conservative per-image
// ceiling. Container deployments can accept more, but every mobile capture uses
// the same portable bound so saved observations remain comparable on either host.
const SANITIZATION_PROFILES = [
  { longestEdge: 2048, compression: 0.86 },
  { longestEdge: 1792, compression: 0.78 },
  { longestEdge: 1536, compression: 0.7 },
  { longestEdge: 1280, compression: 0.62 },
  { longestEdge: 1152, compression: 0.52 },
] as const;

function telemetryFromBase64(
  base64: string,
  stable: boolean,
  width: number,
  height: number,
  byteSize: number,
): ImageTelemetry {
  try {
    const image = Skia.Image.MakeImageFromEncoded(Skia.Data.fromBase64(base64));
    if (!image) throw new Error("Image decode failed");
    const decodedWidth = image.width();
    const decodedHeight = image.height();
    const reader = image as unknown as {
      readPixels: () => Uint8Array | Float32Array | null;
    };
    const pixels = reader.readPixels();
    if (!pixels || pixels.length < 16)
      throw new Error("Image pixels unavailable");

    const scale = pixels instanceof Float32Array ? 1 : 255;
    const pixelCount = Math.floor(pixels.length / 4);
    const sampleStep = Math.max(1, Math.ceil(Math.sqrt(pixelCount / 7_000)));
    let luminanceTotal = 0;
    let highlights = 0;
    let dark = 0;
    let edgeTotal = 0;
    let edgeSamples = 0;
    let laplacianTotal = 0;
    let laplacianSquareTotal = 0;
    let laplacianSamples = 0;
    let samples = 0;

    const luminanceAt = (x: number, y: number) => {
      const offset = (y * decodedWidth + x) * 4;
      const red = Number(pixels[offset] ?? 0) / scale;
      const green = Number(pixels[offset + 1] ?? 0) / scale;
      const blue = Number(pixels[offset + 2] ?? 0) / scale;
      return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
    };

    for (let y = 0; y < decodedHeight; y += sampleStep) {
      for (let x = 0; x < decodedWidth; x += sampleStep) {
        const luminance = luminanceAt(x, y);
        const nextX = x + sampleStep;
        const nextY = y + sampleStep;
        if (nextX < decodedWidth) {
          edgeTotal += Math.abs(luminance - luminanceAt(nextX, y));
          edgeSamples += 1;
        }
        if (nextY < decodedHeight) {
          edgeTotal += Math.abs(luminance - luminanceAt(x, nextY));
          edgeSamples += 1;
        }
        luminanceTotal += luminance;
        if (luminance > 0.94) highlights += 1;
        if (luminance < 0.08) dark += 1;
        samples += 1;
      }
    }
    for (let y = sampleStep; y + sampleStep < decodedHeight; y += sampleStep) {
      for (let x = sampleStep; x + sampleStep < decodedWidth; x += sampleStep) {
        const center = luminanceAt(x, y);
        const laplacian =
          4 * center -
          luminanceAt(x - sampleStep, y) -
          luminanceAt(x + sampleStep, y) -
          luminanceAt(x, y - sampleStep) -
          luminanceAt(x, y + sampleStep);
        laplacianTotal += laplacian;
        laplacianSquareTotal += laplacian * laplacian;
        laplacianSamples += 1;
      }
    }
    const laplacianMean = laplacianTotal / Math.max(1, laplacianSamples);
    const focusVariance = Math.max(
      0,
      laplacianSquareTotal / Math.max(1, laplacianSamples) -
        laplacianMean * laplacianMean,
    );

    image.dispose();
    return {
      edgeStrength: edgeTotal / Math.max(1, edgeSamples),
      focusVariance,
      meanLuminance: luminanceTotal / Math.max(1, samples),
      highlightFraction: highlights / Math.max(1, samples),
      obstructionEstimate: Math.min(1, (dark / Math.max(1, samples)) * 1.4),
      faceDetected: false,
      stable,
      width: decodedWidth,
      height: decodedHeight,
      byteSize,
    };
  } catch {
    return {
      edgeStrength: 0,
      focusVariance: 0,
      meanLuminance: 0,
      highlightFraction: 0,
      obstructionEstimate: 1,
      faceDetected: false,
      stable,
      width,
      height,
      byteSize,
    };
  }
}

async function imageDimensions(
  uri: string,
): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    NativeImage.getSize(
      uri,
      (width, height) => resolve({ width, height }),
      () =>
        reject(new Error("The selected file could not be read as an image.")),
    );
  });
}

async function sanitizeImageCapture(
  uri: string,
  options: {
    stable: boolean;
    source: SanitizedCapture["source"];
  },
): Promise<SanitizedCapture> {
  let manipulatedUri: string | null = null;
  let protectedTempUri: string | null = null;
  try {
    const dimensions = await imageDimensions(uri);
    const sourceLongestEdge = Math.max(dimensions.width, dimensions.height);
    let output: Awaited<ReturnType<typeof manipulateAsync>> | null = null;
    let byteSize = Number.POSITIVE_INFINITY;
    for (const profile of SANITIZATION_PROFILES) {
      const actions =
        sourceLongestEdge > profile.longestEdge
          ? [
              {
                resize:
                  dimensions.width >= dimensions.height
                    ? { width: profile.longestEdge }
                    : { height: profile.longestEdge },
              },
            ]
          : [];
      const candidate = await manipulateAsync(uri, actions, {
        compress: profile.compression,
        format: SaveFormat.JPEG,
        base64: true,
      });
      if (
        manipulatedUri &&
        manipulatedUri !== uri &&
        manipulatedUri !== candidate.uri
      ) {
        await removeFileIfPresent(manipulatedUri);
      }
      manipulatedUri = candidate.uri;
      output = candidate;
      if (!candidate.base64) {
        throw new Error("Could not create a metadata-free image.");
      }
      byteSize = Math.floor((candidate.base64.length * 3) / 4);
      if (byteSize <= TRANSPORT_IMAGE_BYTE_LIMIT) break;
    }
    if (!output?.base64 || byteSize > TRANSPORT_IMAGE_BYTE_LIMIT) {
      throw new Error(
        "The image could not be reduced to the protected upload-size limit. Choose a more tightly framed photo.",
      );
    }
    protectedTempUri = await createStoma3DTempUri("capture", "jpg");
    await FileSystem.writeAsStringAsync(protectedTempUri, output.base64, {
      encoding: FileSystem.EncodingType.Base64,
    });
    const capture = {
      uri: protectedTempUri,
      mimeType: "image/jpeg" as const,
      telemetry: telemetryFromBase64(
        output.base64,
        options.stable,
        output.width,
        output.height,
        byteSize,
      ),
      source: options.source,
      width: output.width,
      height: output.height,
      byteSize,
    };
    protectedTempUri = null;
    return capture;
  } finally {
    if (manipulatedUri && manipulatedUri !== uri) {
      await removeFileIfPresent(manipulatedUri);
    }
    await removeFileIfPresent(protectedTempUri);
  }
}

export async function sanitizeCameraCapture(
  uri: string,
  stable: boolean,
): Promise<SanitizedCapture> {
  return sanitizeImageCapture(uri, { stable, source: "camera" });
}

export async function sanitizeSelectedImage(
  uri: string,
): Promise<SanitizedCapture> {
  return sanitizeImageCapture(uri, {
    stable: true,
    source: "photo_library",
  });
}

export async function sanitizeVideoFrame(
  uri: string,
): Promise<SanitizedCapture> {
  return sanitizeImageCapture(uri, {
    stable: true,
    source: "video_sweep",
  });
}

export function qualityForSanitizedCapture(capture: SanitizedCapture) {
  return evaluateImageTelemetry(capture.telemetry);
}
