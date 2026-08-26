param(
    [string]$OutputPath,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$repositoryPrefix = $repositoryRoot.TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar
) + [System.IO.Path]::DirectorySeparatorChar
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $parentDirectory = Split-Path -Parent $repositoryRoot
    $OutputPath = Join-Path $parentDirectory "OralSight-source.zip"
}

$outputFullPath = [System.IO.Path]::GetFullPath($OutputPath)
$outputParent = Split-Path -Parent $outputFullPath
if (-not (Test-Path -LiteralPath $outputParent -PathType Container)) {
    throw "The ZIP parent directory does not exist: $outputParent"
}
if (Test-Path -LiteralPath $outputFullPath) {
    if (-not $Force) {
        throw "The ZIP already exists. Choose another path or pass -Force: $outputFullPath"
    }
    if (-not (Test-Path -LiteralPath $outputFullPath -PathType Leaf)) {
        throw "The output target is not a file: $outputFullPath"
    }
    Remove-Item -LiteralPath $outputFullPath -Force
}

$relativeFiles = @(
    git -C $repositoryRoot ls-files --cached --others --exclude-standard
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique
if ($LASTEXITCODE -ne 0) {
    throw "Git could not enumerate the source files."
}
if ($relativeFiles.Count -eq 0) {
    throw "No source files were found."
}

$secretFilePatterns = @(
    '(^|/|\\)\.env($|\.)',
    '(^|/|\\)production\.env$',
    '(^|/|\\)[^/\\]+\.env$',
    '(^|/|\\)(id_rsa|id_ed25519|credentials)(\.|$)',
    '\.(pem|p12|pfx|key)$'
)
$unsafeFiles = @(
    foreach ($relativePath in $relativeFiles) {
        $normalized = $relativePath.Replace("\", "/")
        $isPublicExample = $normalized.EndsWith(
            ".env.example",
            [System.StringComparison]::OrdinalIgnoreCase
        ) -or $normalized.EndsWith(
            ".example",
            [System.StringComparison]::OrdinalIgnoreCase
        )
        if ($isPublicExample) {
            continue
        }
        foreach ($pattern in $secretFilePatterns) {
            if ($normalized -match $pattern) {
                $relativePath
                break
            }
        }
    }
)
if ($unsafeFiles.Count -gt 0) {
    throw "Refusing to package secret-like files: $($unsafeFiles -join ', ')"
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::Open(
    $outputFullPath,
    [System.IO.Compression.ZipArchiveMode]::Create
)
try {
    foreach ($relativePath in $relativeFiles) {
        $sourcePath = [System.IO.Path]::GetFullPath(
            (Join-Path $repositoryRoot $relativePath)
        )
        if (-not $sourcePath.StartsWith(
            $repositoryPrefix,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            throw "Refusing to package a path outside the repository: $relativePath"
        }
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            throw "Enumerated source file is missing: $relativePath"
        }
        $entryName = $relativePath.Replace("\", "/")
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $archive,
            $sourcePath,
            $entryName,
            [System.IO.Compression.CompressionLevel]::Optimal
        ) | Out-Null
    }
}
finally {
    $archive.Dispose()
}

$archiveHash = (Get-FileHash -LiteralPath $outputFullPath -Algorithm SHA256).Hash
[pscustomobject]@{
    archive = $outputFullPath
    files = $relativeFiles.Count
    bytes = (Get-Item -LiteralPath $outputFullPath).Length
    sha256 = $archiveHash.ToLowerInvariant()
} | ConvertTo-Json
