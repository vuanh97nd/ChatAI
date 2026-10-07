$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Drawing

$projectRoot = $PSScriptRoot
$logoPath = Join-Path $projectRoot 'logo_chat_ai.png'
$assetsPath = Join-Path $projectRoot 'installer-assets'

if (-not (Test-Path -LiteralPath $logoPath)) {
    throw "Missing robot logo: $logoPath"
}

New-Item -ItemType Directory -Force -Path $assetsPath | Out-Null

$logo = $null

function Draw-Logo {
    param(
        [System.Drawing.Graphics]$Graphics,
        [System.Drawing.Image]$Image,
        [int]$X,
        [int]$Y,
        [int]$BoxSize
    )

    $scale = [Math]::Min(
        $BoxSize / [double]$Image.Width,
        $BoxSize / [double]$Image.Height
    )

    $width = [Math]::Max(1, [int][Math]::Round($Image.Width * $scale))
    $height = [Math]::Max(1, [int][Math]::Round($Image.Height * $scale))

    $left = $X + [int](($BoxSize - $width) / 2)
    $top = $Y + [int](($BoxSize - $height) / 2)

    $Graphics.DrawImage($Image, $left, $top, $width, $height)
}

function New-IconPng {
    param(
        [System.Drawing.Image]$Image,
        [int]$Size
    )

    $bitmap = New-Object System.Drawing.Bitmap($Size, $Size)
    $graphics = $null
    $memory = $null

    try {
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $graphics.Clear([System.Drawing.Color]::Transparent)
        $graphics.InterpolationMode =
            [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.SmoothingMode =
            [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
        $graphics.PixelOffsetMode =
            [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

        $padding = [Math]::Max(1, [int]($Size * 0.04))
        Draw-Logo $graphics $Image $padding $padding ($Size - 2 * $padding)

        $memory = New-Object System.IO.MemoryStream
        $bitmap.Save(
            $memory,
            [System.Drawing.Imaging.ImageFormat]::Png
        )

        # Prevent PowerShell from enumerating individual bytes.
        return ,$memory.ToArray()
    }
    finally {
        if ($memory) { $memory.Dispose() }
        if ($graphics) { $graphics.Dispose() }
        $bitmap.Dispose()
    }
}

function Save-MultiSizeIcon {
    param(
        [System.Drawing.Image]$Image,
        [string]$Destination
    )

    $sizes = @(16, 24, 32, 48, 64, 128, 256)
    $entries = @()

    foreach ($size in $sizes) {
        $entries += [PSCustomObject]@{
            Size = $size
            Data = (New-IconPng $Image $size)
        }
    }

    $stream = $null
    $writer = $null

    try {
        $stream = [System.IO.File]::Create($Destination)
        $writer = New-Object System.IO.BinaryWriter($stream)

        # ICONDIR.
        $writer.Write([UInt16]0)
        $writer.Write([UInt16]1)
        $writer.Write([UInt16]$entries.Count)

        $offset = 6 + 16 * $entries.Count

        foreach ($entry in $entries) {
            $dimension = if ($entry.Size -eq 256) { 0 } else { $entry.Size }

            # ICONDIRENTRY.
            $writer.Write([byte]$dimension)
            $writer.Write([byte]$dimension)
            $writer.Write([byte]0)
            $writer.Write([byte]0)
            $writer.Write([UInt16]1)
            $writer.Write([UInt16]32)
            $writer.Write([UInt32]$entry.Data.Length)
            $writer.Write([UInt32]$offset)

            $offset += $entry.Data.Length
        }

        foreach ($entry in $entries) {
            $writer.Write([byte[]]$entry.Data)
        }

        $writer.Flush()
    }
    finally {
        if ($writer) {
            $writer.Dispose()
        }
        elseif ($stream) {
            $stream.Dispose()
        }
    }
}

function Save-WizardImage {
    param(
        [System.Drawing.Image]$Image,
        [string]$Destination,
        [bool]$Small
    )

    $width = if ($Small) { 55 } else { 164 }
    $height = if ($Small) { 55 } else { 314 }

    $bitmap = New-Object System.Drawing.Bitmap(
        $width,
        $height,
        [System.Drawing.Imaging.PixelFormat]::Format24bppRgb
    )

    $graphics = $null
    $gradient = $null
    $font = $null
    $brush = $null
    $format = $null

    try {
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $graphics.InterpolationMode =
            [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.SmoothingMode =
            [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

        if ($Small) {
            $graphics.Clear([System.Drawing.Color]::White)
            Draw-Logo $graphics $Image 5 5 45
        }
        else {
            $rectangle = New-Object System.Drawing.Rectangle(
                0, 0, $width, $height
            )

            $gradient = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
                $rectangle,
                [System.Drawing.Color]::FromArgb(25, 28, 46),
                [System.Drawing.Color]::FromArgb(49, 35, 92),
                [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
            )

            $graphics.FillRectangle($gradient, $rectangle)
            Draw-Logo $graphics $Image 22 62 120

            $font = New-Object System.Drawing.Font(
                'Segoe UI',
                20,
                [System.Drawing.FontStyle]::Bold,
                [System.Drawing.GraphicsUnit]::Pixel
            )

            $brush = New-Object System.Drawing.SolidBrush(
                [System.Drawing.Color]::White
            )

            $format = New-Object System.Drawing.StringFormat
            $format.Alignment = [System.Drawing.StringAlignment]::Center

            $textRectangle = New-Object System.Drawing.RectangleF(
                0, 205, $width, 45
            )

            $graphics.DrawString(
                'Chat AI',
                $font,
                $brush,
                $textRectangle,
                $format
            )
        }

        $bitmap.Save(
            $Destination,
            [System.Drawing.Imaging.ImageFormat]::Bmp
        )
    }
    finally {
        if ($format) { $format.Dispose() }
        if ($brush) { $brush.Dispose() }
        if ($font) { $font.Dispose() }
        if ($gradient) { $gradient.Dispose() }
        if ($graphics) { $graphics.Dispose() }
        $bitmap.Dispose()
    }
}

try {
    $logo = [System.Drawing.Image]::FromFile($logoPath)

    Save-MultiSizeIcon `
        $logo `
        (Join-Path $assetsPath 'chat_ai.ico')

    Save-WizardImage `
        $logo `
        (Join-Path $assetsPath 'wizard.bmp') `
        $false

    Save-WizardImage `
        $logo `
        (Join-Path $assetsPath 'wizard-small.bmp') `
        $true

    Write-Host 'Generated installer assets:'
    Write-Host '  installer-assets\chat_ai.ico'
    Write-Host '  installer-assets\wizard.bmp'
    Write-Host '  installer-assets\wizard-small.bmp'
}
finally {
    if ($logo) { $logo.Dispose() }
}