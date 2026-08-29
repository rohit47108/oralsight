import { join, resolve } from "node:path";
import { Worker } from "node:worker_threads";

import {
  findInstalledPackageRoot,
  findPnpmVirtualStore,
} from "./pnpm-store-path.mjs";

const pnpmStore = findPnpmVirtualStore(resolve("."));
const packageRoot = findInstalledPackageRoot(pnpmStore, "image-size", "1.2.1");

const workerSource = String.raw`
  const { parentPort, workerData } = require("node:worker_threads");
  const { ICNS } = require(workerData.icns);
  const { findBox } = require(workerData.utils);

  const malformedIcns = Buffer.alloc(16);
  malformedIcns.write("icns", 0, "ascii");
  malformedIcns.writeUInt32BE(16, 4);
  malformedIcns.write("ic07", 8, "ascii");
  malformedIcns.writeUInt32BE(0, 12);
  let rejectedIcns = false;
  try {
    ICNS.calculate(malformedIcns);
  } catch {
    rejectedIcns = true;
  }
  if (!rejectedIcns) throw new Error("Malformed ICNS entry was accepted");

  const zeroSizedBox = Buffer.alloc(8);
  zeroSizedBox.writeUInt32BE(0, 0);
  zeroSizedBox.write("jxlp", 4, "ascii");
  if (findBox(zeroSizedBox, "jxlp", 0) !== undefined) {
    throw new Error("Zero-sized ISO BMFF box was accepted");
  }
  parentPort.postMessage("ok");
`;

const worker = new Worker(workerSource, {
  eval: true,
  workerData: {
    icns: join(packageRoot, "dist/types/icns.js"),
    utils: join(packageRoot, "dist/types/utils.js"),
  },
});

await new Promise((resolvePromise, rejectPromise) => {
  const timeout = setTimeout(async () => {
    await worker.terminate();
    rejectPromise(new Error("Patched image-size regression check timed out"));
  }, 2_000);
  worker.once("message", (message) => {
    clearTimeout(timeout);
    if (message === "ok") resolvePromise();
    else rejectPromise(new Error("Unexpected image-size worker result"));
  });
  worker.once("error", (error) => {
    clearTimeout(timeout);
    rejectPromise(error);
  });
  worker.once("exit", (code) => {
    if (code !== 0) {
      clearTimeout(timeout);
      rejectPromise(new Error(`image-size check exited with code ${code}`));
    }
  });
});

process.stdout.write("Patched image-size parsers reject zero-length loops.\n");
