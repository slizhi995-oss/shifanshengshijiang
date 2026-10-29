param([Parameter(Mandatory=$true)][string]$Manifest, [switch]$IncludeWords)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime] > $null
[Windows.Storage.Streams.IRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime] > $null
[Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime] > $null
[Windows.Graphics.Imaging.SoftwareBitmap,Windows.Graphics.Imaging,ContentType=WindowsRuntime] > $null
[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime] > $null
[Windows.Media.Ocr.OcrResult,Windows.Foundation,ContentType=WindowsRuntime] > $null
$taskMethod = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1
} | Select-Object -First 1
function Get-WinRTResult($operation, [Type]$resultType) {
    $task = $taskMethod.MakeGenericMethod($resultType).Invoke($null, @($operation))
    $task.Wait()
    $task.Result
}
$recognizer = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $recognizer) { throw 'No installed Windows OCR language' }
$jobs = Get-Content -LiteralPath $Manifest -Raw -Encoding UTF8 | ConvertFrom-Json
$timer = [Diagnostics.Stopwatch]::StartNew()
foreach ($job in $jobs) {
    if (Test-Path -LiteralPath $job.output) {
        if (-not $IncludeWords) { continue }
        $cached = Get-Content -LiteralPath $job.output -Raw -Encoding UTF8 | ConvertFrom-Json
        if (@($cached.lines).Count -eq 0 -or $null -ne $cached.lines[0].words) { continue }
    }
    $file = Get-WinRTResult ([Windows.Storage.StorageFile]::GetFileFromPathAsync($job.image)) ([Windows.Storage.StorageFile])
    $stream = Get-WinRTResult ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $bitmap = $null
    try {
        $decoder = Get-WinRTResult ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Get-WinRTResult ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $result = Get-WinRTResult ($recognizer.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        $lines = @($result.Lines | ForEach-Object {
            $words = @($_.Words)
            $xs = @($words | ForEach-Object {$_.BoundingRect.X})
            $ys = @($words | ForEach-Object {$_.BoundingRect.Y})
            $rights = @($words | ForEach-Object {$_.BoundingRect.X + $_.BoundingRect.Width})
            $bottoms = @($words | ForEach-Object {$_.BoundingRect.Y + $_.BoundingRect.Height})
            $lineData = @{text=$_.Text; bbox=@(
                (($xs | Measure-Object -Minimum).Minimum / $job.scale),
                (($ys | Measure-Object -Minimum).Minimum / $job.scale),
                (($rights | Measure-Object -Maximum).Maximum / $job.scale),
                (($bottoms | Measure-Object -Maximum).Maximum / $job.scale)
            )}
            if ($IncludeWords) {
                $lineData.words = @($words | ForEach-Object {
                    @{text=$_.Text; bbox=@(
                        ($_.BoundingRect.X / $job.scale), ($_.BoundingRect.Y / $job.scale),
                        (($_.BoundingRect.X + $_.BoundingRect.Width) / $job.scale),
                        (($_.BoundingRect.Y + $_.BoundingRect.Height) / $job.scale)
                    )}
                })
            }
            $lineData
        })
        @{width=$job.width; height=$job.height; lines=$lines} | ConvertTo-Json -Depth 8 -Compress | Set-Content -LiteralPath $job.output -Encoding UTF8
        Write-Output "OCR page=$($job.page) elapsed=$([int]$timer.Elapsed.TotalSeconds)s"
    } finally {
        if ($null -ne $bitmap) { $bitmap.Dispose() }
        $stream.Dispose()
    }
}
