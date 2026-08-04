import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { z, type ZodType } from "zod";

import {
  analysisResultSchema,
  analyzeMetadataSchema,
  compareMetadataSchema,
  comparisonResultSchema,
  modelCardSchema,
  mouthRegionSchema,
} from "../src/index.ts";

function definition(schema: ZodType): Record<string, unknown> {
  const generated = z.toJSONSchema(schema) as Record<string, unknown>;
  const { $schema: _dialect, ...body } = generated;
  return body;
}

const document = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  $id: "https://oralsight.local/contracts/v1/oralsight-contracts.schema.json",
  title: "OralSight public API contracts",
  description:
    "Generated from the canonical Zod schemas. This result is not a diagnosis.",
  $defs: {
    MouthRegion: definition(mouthRegionSchema),
    AnalyzeMetadata: definition(analyzeMetadataSchema),
    AnalysisResult: definition(analysisResultSchema),
    CompareMetadata: definition(compareMetadataSchema),
    ComparisonResult: definition(comparisonResultSchema),
    ModelCard: definition(modelCardSchema),
  },
};

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const outputPath = resolve(
  scriptDirectory,
  "../generated/oralsight-contracts.schema.json",
);
mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, `${JSON.stringify(document, null, 2)}\n`, "utf8");
console.log(`Generated ${outputPath}`);
