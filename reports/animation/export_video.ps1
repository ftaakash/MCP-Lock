# Adds Morph transitions and timings to MCP-Lock-flow.pptx and renders MCP-Lock-flow.mp4 with PowerPoint.
# Each slide's notes hold its seconds on screen (written by make_video.js).
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$app = New-Object -ComObject PowerPoint.Application
$deck = $app.Presentations.Open("$dir\MCP-Lock-flow.pptx", $false, $false, $false)
$morph = 3953  # ppEffectMorphByObject
foreach ($s in $deck.Slides) {
    $secs = [double]($s.NotesPage.Shapes.Placeholders(2).TextFrame.TextRange.Text.Trim())
    $tr = $s.SlideShowTransition
    if ($s.SlideIndex -gt 1) { $tr.EntryEffect = $morph; $tr.Duration = 1.1 }
    $tr.AdvanceOnClick = 0
    $tr.AdvanceOnTime = -1
    $tr.AdvanceTime = $secs
}
$deck.Save()
$mp4 = "$dir\MCP-Lock-flow.mp4"
if (Test-Path $mp4) { Remove-Item $mp4 }
$deck.CreateVideo($mp4, $true, 5, 1080, 30, 90)
while ($deck.CreateVideoStatus -eq 1 -or $deck.CreateVideoStatus -eq 2) { Start-Sleep -Seconds 2 }
"status: $($deck.CreateVideoStatus) (3 = done)"
$deck.Close()
$app.Quit()
