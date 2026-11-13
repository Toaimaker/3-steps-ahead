# L'OCR di Windows (Windows.Media.Ocr, gia' nel sistema) come servizio: legge da stdin un percorso d'immagine per riga e
# scrive su stdout una riga JSON con le parole riconosciute e i loro riquadri, in pixel dell'immagine.
# Nessun download, nessun programma nuovo: e' l'API WinRT che Windows usa per lo strumento di cattura.
# Uso (lo lancia Companion/App/Overlay/ocr.py): powershell -NoProfile -ExecutionPolicy Bypass -File ocr_windows.ps1 [lingua]
param([string]$Lingua = "en-US")
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Attendi($op, [Type]$tipo) {
    $t = $asTask.MakeGenericMethod($tipo).Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result
}
$lang = New-Object Windows.Globalization.Language($Lingua)
$motore = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
if ($null -eq $motore) { $motore = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
if ($null -eq $motore) { Write-Output '{"errore":"nessun motore OCR"}'; exit 1 }
Write-Output ('{"pronto":"' + $motore.RecognizerLanguage.LanguageTag + '","max":' + [Windows.Media.Ocr.OcrEngine]::MaxImageDimension + '}')
while ($true) {
    $riga = [Console]::In.ReadLine()
    if ($null -eq $riga -or $riga -eq "") { break }
    try {
        $f = Attendi ([Windows.Storage.StorageFile]::GetFileFromPathAsync($riga)) ([Windows.Storage.StorageFile])
        $s = Attendi ($f.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $dec = Attendi ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($s)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bmp = Attendi ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $ris = Attendi ($motore.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
        $righe = @()
        foreach ($l in $ris.Lines) {
            $parole = @()
            foreach ($w in $l.Words) {
                $r = $w.BoundingRect
                $parole += @{ t = $w.Text; x = [int]$r.X; y = [int]$r.Y; w = [int]$r.Width; h = [int]$r.Height }
            }
            $righe += , @{ t = $l.Text; p = $parole }
        }
        $s.Dispose(); $bmp.Dispose()
        Write-Output (ConvertTo-Json -Compress -Depth 5 @{ righe = $righe })
    } catch {
        Write-Output (ConvertTo-Json -Compress @{ errore = $_.Exception.Message })
    }
}
