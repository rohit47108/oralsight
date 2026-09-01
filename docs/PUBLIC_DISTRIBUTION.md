# Public source and private model bundle

The Stoma3D source code is published under the MIT License. Third-party
packages and assets keep their own licenses as listed in
`docs/licenses-model-cards`.

The public repository includes the CC BY 4.0 anatomy model and the MIT-licensed
face-presence model. It does not include the Autooral-assisted candidate
segmentation weight. That weight is used only by the academic competition
deployment and is supplied to the inference service through a private release
bundle.

## Private release bundle

The private directory is `services/inference/private-release/` and is ignored by
Git. A working bundle contains:

- `release-manifest.json`
- `anatomy.onnx`
- `segmentation.onnx`

Set `STOMA3D_RELEASE_MANIFEST_PATH` to the absolute path of the private
manifest. The service verifies every artifact hash and runs a startup inference
check before enabling a head. Missing or changed files leave that head
unavailable instead of loading an unverified model.

The checked-in `services/inference/release/release-manifest.json` is the public
source manifest. It enables anatomy matching and records candidate segmentation
as externally supplied. It is safe for public builds but does not provide
candidate masks by itself.

For a full competition container deployment, run this from
`services/inference` after preparing the bundle:

```powershell
docker build -f Dockerfile.private -t stoma3d-inference:competition .
```

That build requires the ignored directory, so a public clone cannot
accidentally produce or redistribute the private model image. Do not commit the
bundle or place its contents in a public download.
