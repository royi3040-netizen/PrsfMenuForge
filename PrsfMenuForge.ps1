# PrsfMenuForge — Windows 11 right-click menu manager
# PowerShell 5.1 / WPF. Source code; no compiled binary or external modules.
# Scope: classic shell verbs and legacy COM context-menu handlers.
# Safe operation: export backups before edits, reversible hide rather than delete.

if ([System.Threading.Thread]::CurrentThread.ApartmentState -ne 'STA') {
    [System.Windows.MessageBox]::Show('יש להפעיל את התוכנה דרך הקובץ "הפעל.bat".','PrsfMenuForge')
    return
}

Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Drawing, System.Windows.Forms

$script:ScriptFile = $MyInvocation.MyCommand.Path
$script:AppDir = Join-Path $env:LOCALAPPDATA 'PrsfMenuForge'
$script:BackupDir = Join-Path $script:AppDir 'Backups'
[void](New-Item -ItemType Directory -Path $script:BackupDir -Force)
$script:Entries = [System.Collections.Generic.List[object]]::new()
$script:Category = 'all'
$script:Search = ''
$script:IconCache = @{}
$script:BlockPath = 'Registry::HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Shell Extensions\Blocked'
$script:IsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

# What was registered and where. The modern Windows 11 IExplorerCommand / packaged
# menu and Windows' built-in commands cannot be fully discovered through these keys.
$script:Locations = @(
    @{Group='desktop'; Name='שולחן עבודה'; Relative='Directory\Background'},
    @{Group='desktop'; Name='שולחן עבודה (מורחב)'; Relative='DesktopBackground'},
    @{Group='folders'; Name='תיקיות'; Relative='Directory'},
    @{Group='folders'; Name='כל התיקיות'; Relative='Folder'},
    @{Group='files'; Name='כל הקבצים'; Relative='*'},
    @{Group='files'; Name='פריטי מערכת הקבצים'; Relative='AllFilesystemObjects'},
    @{Group='drives'; Name='כוננים'; Relative='Drive'}
)
$script:Roots = @(
    @{Path='Registry::HKEY_CURRENT_USER\Software\Classes'; Short='HKEY_CURRENT_USER\Software\Classes'; Source='משתמש נוכחי'},
    @{Path='Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Classes'; Short='HKEY_LOCAL_MACHINE\SOFTWARE\Classes'; Source='כל המשתמשים'}
)
$script:SystemVerbs = @('open','opennew','explore','find','properties','cut','copy','paste','delete','rename','new','view','sort','refresh','runas','runasuser','print','printto','cmd','powershell','search','openas')

function Get-RegKey([string]$Path) {
    try { return Get-Item -LiteralPath $Path -ErrorAction Stop } catch { return $null }
}
function Get-RegValue($Key, [string]$Name) {
    if ($null -eq $Key) { return $null }
    try { return $Key.GetValue($Name, $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames) } catch { return $null }
}
function Has-RegValue($Key, [string]$Name) {
    if ($null -eq $Key) { return $false }
    try { return $Key.GetValueNames() -contains $Name } catch { return $false }
}
function Resolve-RegText([string]$Text) {
    if (-not $Text) { return '' }
    if ($Text.StartsWith('@')) { return '' }
    return $Text.Replace('&','').Trim()
}
function Find-Executable([string]$Command, [string]$IconSpec) {
    foreach ($candidate in @($IconSpec,$Command)) {
        if (-not $candidate) { continue }
        $expanded = [Environment]::ExpandEnvironmentVariables($candidate)
        if ($expanded.StartsWith('@')) { $expanded = $expanded.Substring(1) }
        if ($expanded -match '^\s*"([^"]+\.(?:exe|dll|ico))"') { $p = $Matches[1] }
        elseif ($expanded -match '^\s*([^,]+?\.(?:exe|dll|ico))(?:,[-\d]+)?(?:\s|$)') { $p = $Matches[1].Trim() }
        else { continue }
        if (Test-Path -LiteralPath $p -PathType Leaf) { return $p }
    }
    return ''
}
function Get-Image([string]$ExePath) {
    if (-not $ExePath) { return $null }
    if ($script:IconCache.ContainsKey($ExePath)) { return $script:IconCache[$ExePath] }
    $bitmap = $null
    try {
        $ico = [System.Drawing.Icon]::ExtractAssociatedIcon($ExePath)
        if ($null -ne $ico) {
            $bitmap = [System.Windows.Interop.Imaging]::CreateBitmapSourceFromHIcon(
                $ico.Handle, [System.Windows.Int32Rect]::Empty,
                [System.Windows.Media.Imaging.BitmapSizeOptions]::FromWidthAndHeight(24,24))
            $bitmap.Freeze()
            $ico.Dispose()
        }
    } catch { }
    $script:IconCache[$ExePath] = $bitmap
    return $bitmap
}
function Get-SourceName([string]$Verb, [string]$Path, [string]$Friendly) {
    $s = "$Verb $Path $Friendly"
    if ($s -match 'git[_\- ]|git-bash|git-gui') { return 'Git' }
    if ($s -match 'AnyCode|visual studio|devenv') { return 'Visual Studio' }
    if ($s -match 'nvidia') { return 'NVIDIA' }
    if ($s -match '7-zip|7zfm|7zip') { return '7-Zip' }
    if ($s -match 'notepad\+\+') { return 'Notepad++' }
    if ($s -match 'PrsfCM_') { return 'נוסף באמצעות Prsf' }
    if ($s -match '\\Windows\\|^cmd |^powershell ') { return 'Windows' }
    if ($Path -and (Test-Path -LiteralPath $Path -PathType Leaf)) {
        try {
            $product = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($Path).ProductName
            if (-not [string]::IsNullOrWhiteSpace($product)) { return $product }
        } catch { }
    }
    return 'יישום / תוסף'
}
function Is-CoreEntry([string]$Verb,[string]$Origin,[string]$Cmd) {
    if ($script:SystemVerbs -contains $Verb.ToLowerInvariant()) { return $true }
    if ($Verb -match '^(Windows|Explorer|ModernSharing|Shell)') { return $true }
    if ($Origin -match '^Microsoft Windows') { return $true }
    return $false
}
function Get-HandlerGuid($Key, [string]$ChildName) {
    $v = [string](Get-RegValue $Key '')
    if ($v -match '^\{[0-9a-fA-F\-]{36}\}$') { return $v }
    if ($ChildName -match '^\{[0-9a-fA-F\-]{36}\}$') { return $ChildName }
    return ''
}
function Is-Blocked([string]$Guid) {
    if (-not $Guid) { return $false }
    foreach ($bp in @($script:BlockPath,'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Shell Extensions\Blocked')) {
        if (Has-RegValue (Get-RegKey $bp) $Guid) { return $true }
    }
    return $false
}
function New-Entry($Category,$Location,$Root,$Key,$Type,$Name) {
    $regPath = $Key.Name
    $cmd = ''
    $iconSpec = [string](Get-RegValue $Key 'Icon')
    $label = Resolve-RegText ([string](Get-RegValue $Key 'MUIVerb'))
    if (-not $label) { $label = Resolve-RegText ([string](Get-RegValue $Key '')) }
    if (-not $label) { $label = $Name.Replace('_',' ') }
    $clsid = ''
    $hasProgrammatic = Has-RegValue $Key 'ProgrammaticAccessOnly'
    $legacy = Has-RegValue $Key 'LegacyDisable'
    $shift = Has-RegValue $Key 'Extended'
    if ($Type -eq 'פקודה') {
        $commandKey = Get-RegKey ("Registry::" + $regPath + '\command')
        $cmd = [string](Get-RegValue $commandKey '')
    } else {
        $clsid = Get-HandlerGuid $Key $Name
        if ($clsid) {
            $comKey = Get-RegKey ("Registry::HKEY_CLASSES_ROOT\CLSID\$clsid")
            $comName = Resolve-RegText ([string](Get-RegValue $comKey ''))
            if ($comName) { $label = $comName }
            $dllKey = Get-RegKey ("Registry::HKEY_CLASSES_ROOT\CLSID\$clsid\InProcServer32")
            $cmd = [string](Get-RegValue $dllKey '')
            if (-not $iconSpec) { $iconSpec = $cmd }
        }
    }
    $exe = Find-Executable $cmd $iconSpec
    $origin = Get-SourceName $Name $exe $label
    $core = Is-CoreEntry $Name $origin $cmd
    if ($Type -eq 'תוסף' -and -not $clsid) { $core = $true }
    if ($Type -eq 'תוסף' -and ($exe -match '(?i)\\Windows\\(System32|SysWOW64)\\')) { $core = $true }
    $blocked = if ($Type -eq 'תוסף') { Is-Blocked $clsid } else { $false }
    $status = if ($hasProgrammatic -or $legacy -or $blocked) { 'מוסתר' }
              elseif ($shift) { 'Shift בלבד' }
              else { 'רשום בתפריט' }
    $editable = -not $core
    return [PSCustomObject]@{
        Name=$label; NameKey=$Name; Category=$Category; Location=$Location
        Type=$Type; Origin=$origin; Source=$Root.Source; RegistryPath=$regPath
        Command=$cmd; IconSource=(Get-Image $exe); ExePath=$exe
        Guid=$clsid; Status=$status; IsCore=$core; Editable=$editable
        HasProgrammatic=$hasProgrammatic; HasLegacy=$legacy; IsBlocked=$blocked
        ShiftOnly=$shift; IsOwn=$Name.StartsWith('PrsfCM_')
    }
}
function Reload-Entries {
    $script:Entries.Clear()
    foreach ($loc in $script:Locations) {
        foreach ($root in $script:Roots) {
            foreach ($t in @('shell','shellex\ContextMenuHandlers')) {
                $base = "$($root.Path)\$($loc.Relative)\$t"
                $key = Get-RegKey $base
                if (-not $key) { continue }
                try { $children = @(Get-ChildItem -LiteralPath $base -ErrorAction Stop) } catch { continue }
                foreach ($child in $children) {
                    try {
                        $keyName = [string]$child.PSChildName
                        if (-not $keyName) { $keyName = ($child.Name -split '\\')[-1] }
                        $rec = New-Entry $loc.Group $loc.Name $root $child $(if ($t -eq 'shell') { 'פקודה' } else { 'תוסף' }) $keyName
                        $script:Entries.Add($rec)
                    } catch { continue }
                }
            }
        }
    }
    Show-Entries
}
function Save-Backup([string]$FullRegPath) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $short = ($FullRegPath -split '\\')[-1] -replace '[^a-zA-Z0-9_\-]','_'
    $file = Join-Path $script:BackupDir "$stamp-$short.reg"
    $null = & reg.exe export $FullRegPath $file /y 2>$null
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $file)) {
        throw "לא ניתן ליצור גיבוי של $FullRegPath. לא בוצע שינוי."
    }
    return $file
}
function Notify-Result([string]$Msg) {
    [System.Windows.MessageBox]::Show($Msg,'PrsfMenuForge','OK','Information') | Out-Null
}
function Fail([string]$Msg) {
    [System.Windows.MessageBox]::Show($Msg,'PrsfMenuForge','OK','Warning') | Out-Null
}

$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="PrsfMenuForge — ניהול לחיצה ימנית" Width="1200" Height="760"
        MinWidth="950" MinHeight="600" WindowStartupLocation="CenterScreen"
        Background="#10151E" Foreground="#EFF4FF" FlowDirection="RightToLeft" FontFamily="Segoe UI">
 <Window.Resources>
  <SolidColorBrush x:Key="Panel" Color="#192230"/>
  <SolidColorBrush x:Key="Stroke" Color="#314050"/>
  <Style x:Key="Action" TargetType="Button">
   <Setter Property="Foreground" Value="#EEF5FF"/><Setter Property="Background" Value="#25354A"/>
   <Setter Property="BorderBrush" Value="#3B5268"/><Setter Property="BorderThickness" Value="1"/>
   <Setter Property="Padding" Value="14,9"/><Setter Property="Margin" Value="3"/>
   <Setter Property="Cursor" Value="Hand"/><Setter Property="FontSize" Value="13"/>
  </Style>
  <Style x:Key="CategoryButton" TargetType="Button" BasedOn="{StaticResource Action}">
   <Setter Property="HorizontalContentAlignment" Value="Right"/><Setter Property="Margin" Value="0,0,0,7"/>
   <Setter Property="FontSize" Value="15"/><Setter Property="Padding" Value="14,13"/>
  </Style>
  <Style TargetType="TextBox">
   <Setter Property="Background" Value="#111B28"/><Setter Property="Foreground" Value="#F4F7FF"/>
   <Setter Property="BorderBrush" Value="#3B5268"/><Setter Property="Padding" Value="10,8"/>
   <Setter Property="CaretBrush" Value="White"/>
  </Style>
  <Style TargetType="DataGridRow">
    <Setter Property="Background" Value="#192230"/><Setter Property="Foreground" Value="#E9F2FF"/>
    <Setter Property="Height" Value="43"/><Setter Property="BorderBrush" Value="#2F3C4A"/>
  </Style>
 </Window.Resources>
 <Grid Margin="17">
  <Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="*"/><RowDefinition Height="Auto"/></Grid.RowDefinitions>
  <Grid Grid.Row="0" Margin="0,0,0,15">
   <Grid.ColumnDefinitions><ColumnDefinition Width="*"/><ColumnDefinition Width="Auto"/></Grid.ColumnDefinitions>
   <StackPanel>
    <TextBlock Text="מנהל תפריט הלחיצה הימנית" FontSize="27" FontWeight="Bold"/>
    <TextBlock Text="הצגה, הסתרה והוספת פקודות — בלי למחוק את התוכנות" FontSize="14" Foreground="#9FB3C9" Margin="0,5,0,0"/>
   </StackPanel>
   <StackPanel Grid.Column="1" Orientation="Horizontal" VerticalAlignment="Center">
    <Button x:Name="refreshBtn" Content="⟳  רענון" Style="{StaticResource Action}"/>
    <Button x:Name="backupBtn" Content="▣  גיבויים" Style="{StaticResource Action}"/>
    <Button x:Name="adminBtn" Content="⚿  הפעל כמנהל" Style="{StaticResource Action}"/>
   </StackPanel>
  </Grid>
  <Grid Grid.Row="1">
   <Grid.ColumnDefinitions><ColumnDefinition Width="180"/><ColumnDefinition Width="10"/><ColumnDefinition Width="*"/></Grid.ColumnDefinitions>
   <Border Background="{StaticResource Panel}" BorderBrush="{StaticResource Stroke}" BorderThickness="1" CornerRadius="9" Grid.Column="0" Padding="12">
    <StackPanel>
     <TextBlock Text="איפה לוחצים?" FontWeight="Bold" FontSize="16" Margin="3,3,3,18"/>
     <Button x:Name="allBtn" Style="{StaticResource CategoryButton}" Content="▦   הכול"/>
     <Button x:Name="desktopBtn" Style="{StaticResource CategoryButton}" Content="▣   שולחן העבודה"/>
     <Button x:Name="foldersBtn" Style="{StaticResource CategoryButton}" Content="▤   תיקיות"/>
     <Button x:Name="filesBtn" Style="{StaticResource CategoryButton}" Content="▥   קבצים"/>
     <Button x:Name="drivesBtn" Style="{StaticResource CategoryButton}" Content="◉   כוננים"/>
     <Border Background="#11263A" BorderBrush="#305171" BorderThickness="1" CornerRadius="7" Padding="10" Margin="0,25,0,0">
      <StackPanel>
       <TextBlock Text="הגנה מובנית" Foreground="#7AC7FC" FontWeight="SemiBold"/>
       <TextBlock Text="לפני כל שינוי נשמר גיבוי. פקודות מערכת מוגנות." TextWrapping="Wrap" FontSize="12" Foreground="#C4D6EB" Margin="0,6,0,0"/>
      </StackPanel>
     </Border>
    </StackPanel>
   </Border>
   <Grid Grid.Column="2">
    <Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="*"/><RowDefinition Height="160"/><RowDefinition Height="Auto"/></Grid.RowDefinitions>
    <Grid Grid.Row="0" Margin="0,0,0,10">
     <Grid.ColumnDefinitions><ColumnDefinition Width="*"/><ColumnDefinition Width="Auto"/></Grid.ColumnDefinitions>
     <TextBox x:Name="searchBox" FontSize="15" ToolTip="חיפוש בשם, בתוכנה, במקור או במפתח" />
     <TextBlock x:Name="counterText" Grid.Column="1" Foreground="#9EB7CE" VerticalAlignment="Center" Margin="15,0,10,0"/>
    </Grid>
    <DataGrid x:Name="entriesGrid" Grid.Row="1" Background="#192230" Foreground="#F1F5FA"
         BorderBrush="#314050" BorderThickness="1" HeadersVisibility="Column"
         AutoGenerateColumns="False" CanUserAddRows="False" CanUserDeleteRows="False"
         IsReadOnly="True" GridLinesVisibility="Horizontal" RowHeaderWidth="0"
         AlternatingRowBackground="#1F2A3A" HorizontalScrollBarVisibility="Auto"
         SelectionMode="Single" SelectionUnit="FullRow">
     <DataGrid.ColumnHeaderStyle>
       <Style TargetType="DataGridColumnHeader"><Setter Property="Background" Value="#25364A"/><Setter Property="Foreground" Value="White"/><Setter Property="Padding" Value="10"/><Setter Property="FontWeight" Value="SemiBold"/></Style>
     </DataGrid.ColumnHeaderStyle>
     <DataGrid.Columns>
      <DataGridTemplateColumn Header="סמל" Width="46">
       <DataGridTemplateColumn.CellTemplate>
        <DataTemplate>
         <Grid Width="24" Height="24">
          <TextBlock x:Name="fallbackIcon" Text="◈" Foreground="#77B9E8" FontSize="21" TextAlignment="Center" Visibility="Collapsed"/>
          <Image Source="{Binding IconSource}" Width="23" Height="23"/>
         </Grid>
         <DataTemplate.Triggers>
          <DataTrigger Binding="{Binding IconSource}" Value="{x:Null}">
           <Setter TargetName="fallbackIcon" Property="Visibility" Value="Visible"/>
          </DataTrigger>
         </DataTemplate.Triggers>
        </DataTemplate>
       </DataGridTemplateColumn.CellTemplate>
      </DataGridTemplateColumn>
      <DataGridTextColumn Header="שם בתפריט" Binding="{Binding Name}" Width="2*"/>
      <DataGridTextColumn Header="תוכנה" Binding="{Binding Origin}" Width="1.3*"/>
      <DataGridTextColumn Header="היכן מופיע" Binding="{Binding Location}" Width="1.4*"/>
      <DataGridTextColumn Header="סוג" Binding="{Binding Type}" Width=".8*"/>
      <DataGridTextColumn Header="מצב" Binding="{Binding Status}" Width="1.0*"/>
      <DataGridTextColumn Header="מקור רישום" Binding="{Binding Source}" Width="1.2*"/>
     </DataGrid.Columns>
    </DataGrid>
    <Border Grid.Row="2" Background="{StaticResource Panel}" BorderBrush="{StaticResource Stroke}" BorderThickness="1" CornerRadius="8" Margin="0,10,0,0" Padding="12">
     <Grid><Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/></Grid.RowDefinitions>
      <TextBlock x:Name="detailTitle" Text="בחר פריט להצגת פרטים" FontWeight="Bold" FontSize="16"/>
      <TextBlock x:Name="detailNote" Grid.Row="1" Foreground="#A7C1D8" Margin="0,5,0,7" FontSize="12" TextWrapping="Wrap"/>
      <TextBox x:Name="pathBox" Grid.Row="2" IsReadOnly="True" FontSize="11" Height="31" FlowDirection="LeftToRight"/>
      <TextBox x:Name="commandBox" Grid.Row="3" IsReadOnly="True" FontSize="11" Margin="0,5,0,0" Height="31" FlowDirection="LeftToRight"/>
     </Grid>
    </Border>
    <Grid Grid.Row="3" Margin="0,11,0,0">
     <Grid.ColumnDefinitions><ColumnDefinition Width="*"/><ColumnDefinition Width="Auto"/></Grid.ColumnDefinitions>
     <StackPanel Orientation="Horizontal">
      <Button x:Name="addBtn" Style="{StaticResource Action}" Background="#137ABA" Content="✚  הוסף תוכנה"/>
      <Button x:Name="toggleBtn" Style="{StaticResource Action}" Content="הסתר / החזר" IsEnabled="False"/>
      <Button x:Name="deleteOwnBtn" Style="{StaticResource Action}" Content="מחק תוספת שלי" IsEnabled="False"/>
     </StackPanel>
     <TextBlock x:Name="adminText" Grid.Column="1" VerticalAlignment="Center" Foreground="#B7D0E8"/>
    </Grid>
   </Grid>
  </Grid>
  <TextBlock Grid.Row="2" Text="המידע מבוסס על רישום Windows. חלק מהפריטים הדינמיים של Windows 11 לא ניתנים לזיהוי או לשינוי בכלי זה." Foreground="#99AFC6" Margin="3,12,3,0" FontSize="12"/>
 </Grid>
</Window>
'@
try { $script:Window = [Windows.Markup.XamlReader]::Parse($xaml) }
catch { [System.Windows.MessageBox]::Show($_.Exception.Message,'שגיאה בטעינת הממשק'); return }

foreach ($name in @('entriesGrid','searchBox','counterText','allBtn','desktopBtn','foldersBtn','filesBtn','drivesBtn','refreshBtn','backupBtn','adminBtn','adminText','detailTitle','detailNote','pathBox','commandBox','addBtn','toggleBtn','deleteOwnBtn')) {
    Set-Variable -Scope Script -Name $name -Value $script:Window.FindName($name)
}
$script:adminText.Text = if ($script:IsAdmin) { 'הרשאות מנהל פעילות' } else { 'לשינוי פריטי מערכת ייתכן שתידרש הרשאת מנהל' }
if ($script:IsAdmin) { $script:adminBtn.Visibility = 'Collapsed' }

function Show-Entries {
    $match = @($script:Entries | Where-Object {
        ($script:Category -eq 'all' -or $_.Category -eq $script:Category) -and
        ((-not $script:Search) -or ("$($_.Name) $($_.NameKey) $($_.Origin) $($_.Source) $($_.Location) $($_.RegistryPath)" -like "*$($script:Search)*"))
    } | Sort-Object Origin,Name)
    $script:entriesGrid.ItemsSource = $match
    $script:counterText.Text = "$( $match.Count ) פריטים"
    $script:detailTitle.Text = 'בחר פריט להצגת פרטים'
    $script:detailNote.Text = ''
    $script:pathBox.Text = ''
    $script:commandBox.Text = ''
    $script:toggleBtn.IsEnabled = $false
    $script:deleteOwnBtn.IsEnabled = $false
}
function Update-Detail {
    $e = $script:entriesGrid.SelectedItem
    if (-not $e) { return }
    $script:detailTitle.Text = "$($e.Name)  ·  $($e.Status)"
    $script:pathBox.Text = $e.RegistryPath
    $script:commandBox.Text = $e.Command
    $note = if ($e.IsCore) { 'פריט מערכת / פריט מוגן: מוצג למידע בלבד.' }
            elseif ($e.Type -eq 'תוסף') { 'תוסף COM: ההסתרה היא לפי מזהה התוסף, ולכן עשויה להשפיע על מיקומים נוספים.' }
            elseif ($e.HasLegacy) { 'פריט מוסתר באמצעות LegacyDisable של תוכנה אחרת. אפשרות השינוי אינה זמינה.' }
            elseif ($e.ShiftOnly) { 'מוגדר להופיע רק בלחיצה ימנית תוך החזקת Shift.' }
            else { 'אפשר להסתיר ולהחזיר ללא הסרת התוכנה. נשמר גיבוי לפני השינוי.' }
    $script:detailNote.Text = "$note  |  $($e.Source)"
    $script:toggleBtn.IsEnabled = $e.Editable -and (-not $e.HasLegacy)
    $script:toggleBtn.Content = if ($e.Status -eq 'מוסתר') { '◉  הצג מחדש' } else { '◌  הסתר מהתפריט' }
    $script:deleteOwnBtn.IsEnabled = $e.IsOwn -and $e.Source -eq 'משתמש נוכחי'
}
function Perform-Toggle {
    $entry = $script:entriesGrid.SelectedItem
    if (-not $entry -or -not $entry.Editable) { return }
    if ($entry.Type -eq 'תוסף' -and -not $entry.Guid) { Fail 'לא זוהה מזהה התוסף ולכן לא ניתן לשנות אותו.'; return }
    $doingHide = ($entry.Status -ne 'מוסתר')
    $action = if ($doingHide) { 'להסתיר' } else { 'להציג מחדש' }
    $scopeWarning = if ($entry.Type -eq 'תוסף') { "`nחשוב: התוסף עשוי להופיע גם במקומות אחרים." } else { '' }
    $question = "האם $action את הפריט '$($entry.Name)'?$scopeWarning`n`nהתוכנה לא תוסר מהמחשב, והפעולה תהיה ניתנת לביטול."
    if ([System.Windows.MessageBox]::Show($question,'אישור שינוי','YesNo','Question') -ne 'Yes') { return }
    try {
        if ($entry.Type -eq 'פקודה') {
            [void](Save-Backup $entry.RegistryPath)
            $key = Get-RegKey ('Registry::' + $entry.RegistryPath)
            if (-not $key) { throw 'המפתח כבר אינו קיים.' }
            if ($doingHide) {
                New-ItemProperty -LiteralPath ('Registry::' + $entry.RegistryPath) -Name 'ProgrammaticAccessOnly' -Value '' -PropertyType String -Force -ErrorAction Stop | Out-Null
            } else {
                Remove-ItemProperty -LiteralPath ('Registry::' + $entry.RegistryPath) -Name 'ProgrammaticAccessOnly' -ErrorAction Stop
            }
        } else {
            $currentBlock = Get-RegKey $script:BlockPath
            if ($currentBlock) { [void](Save-Backup ($script:BlockPath -replace '^Registry::','')) }
            else {
                Add-Content -Path (Join-Path $script:AppDir 'added-keys.txt') -Value "Created new Blocked key at $(Get-Date -Format o)" -Encoding UTF8
                $b = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Software\Microsoft\Windows\CurrentVersion\Shell Extensions\Blocked')
                if (-not $b) { throw 'לא ניתן ליצור מפתח חסימה.' }
                $b.Close()
            }
            if ($doingHide) {
                New-ItemProperty -LiteralPath $script:BlockPath -Name $entry.Guid -Value $entry.Name -PropertyType String -Force -ErrorAction Stop | Out-Null
            } else {
                if (-not (Has-RegValue (Get-RegKey $script:BlockPath) $entry.Guid)) {
                    throw 'ההסתרה מבוצעת ברמת המחשב. נדרשות הרשאות מנהל או פעולה ידנית.'
                }
                Remove-ItemProperty -LiteralPath $script:BlockPath -Name $entry.Guid -ErrorAction Stop
            }
        }
        Reload-Entries
        Notify-Result "השינוי נשמר. ייתכן שתצטרך לסגור ולפתוח את סייר Windows כדי לראות את התוצאה.`n`nגיבויים: $script:BackupDir"
    } catch {
        Fail "השינוי לא הושלם: $($_.Exception.Message)`n`nאם הרשאת הגישה נדחתה, הפעל את הכלי כמנהל."
    }
}

$addXaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
    Title="הוספת תוכנה לתפריט" Width="570" Height="390" WindowStartupLocation="CenterOwner"
    ResizeMode="NoResize" Background="#172130" Foreground="White" FontFamily="Segoe UI" FlowDirection="RightToLeft">
 <Window.Resources>
  <Style TargetType="TextBox"><Setter Property="Background" Value="#101925"/><Setter Property="Foreground" Value="White"/><Setter Property="BorderBrush" Value="#52637A"/><Setter Property="Padding" Value="8"/></Style>
  <Style TargetType="Button"><Setter Property="Background" Value="#2D4968"/><Setter Property="Foreground" Value="White"/><Setter Property="Padding" Value="14,8"/><Setter Property="Margin" Value="3"/></Style>
 </Window.Resources>
 <Grid Margin="20"><Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/><RowDefinition Height="*"/></Grid.RowDefinitions>
  <TextBlock Text="שם שיופיע בתפריט" FontSize="14"/>
  <TextBox x:Name="labelInput" Grid.Row="1" Height="35" Margin="0,7,0,16"/>
  <TextBlock Text="קובץ התוכנה (.exe)" Grid.Row="2"/>
  <Grid Grid.Row="3" Margin="0,7,0,16"><Grid.ColumnDefinitions><ColumnDefinition Width="*"/><ColumnDefinition Width="Auto"/></Grid.ColumnDefinitions>
   <TextBox x:Name="exeInput" Grid.Column="0" Height="35" FlowDirection="LeftToRight"/>
   <Button x:Name="chooseExe" Grid.Column="1" Content="בחירה..."/>
  </Grid>
  <StackPanel Grid.Row="4" Orientation="Horizontal">
    <TextBlock Text="הצג בלחיצה ימנית על:" VerticalAlignment="Center" Margin="0,0,0,0"/>
    <ComboBox x:Name="areaInput" Width="188" SelectedIndex="0" Margin="10,0" Background="#24354A" Foreground="Black">
     <ComboBoxItem Content="שולחן העבודה" Tag="Directory\Background"/>
     <ComboBoxItem Content="תיקייה" Tag="Directory"/>
     <ComboBoxItem Content="קובץ" Tag="*"/>
     <ComboBoxItem Content="כונן" Tag="Drive"/>
    </ComboBox>
  </StackPanel>
  <Grid Grid.Row="5" Margin="0,16,0,0"><Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="*"/></Grid.RowDefinitions>
    <CheckBox x:Name="passPath" Grid.Row="0" Content="העבר לתוכנה את נתיב התיקייה / הקובץ שעליו לחצתי" IsChecked="False" FontSize="12"/>
    <StackPanel Grid.Row="1" Orientation="Horizontal" HorizontalAlignment="Left" VerticalAlignment="Bottom">
     <Button x:Name="createBtn" Content="✚  הוסף לתפריט" Background="#176DA6"/>
     <Button x:Name="cancelBtn" Content="ביטול"/>
    </StackPanel>
  </Grid>
 </Grid>
</Window>
'@
function Open-AddDialog {
    $script:dlg = [Windows.Markup.XamlReader]::Parse($addXaml)
    $script:dlg.Owner = $script:Window
    $script:labelIn = $script:dlg.FindName('labelInput')
    $script:exeIn = $script:dlg.FindName('exeInput')
    $script:scopeIn = $script:dlg.FindName('areaInput')
    $script:passIn = $script:dlg.FindName('passPath')
    $script:dlg.FindName('chooseExe').Add_Click({
        $f = New-Object System.Windows.Forms.OpenFileDialog
        $f.Filter = 'תוכנות (*.exe)|*.exe'
        $f.CheckFileExists = $true
        if ($f.ShowDialog() -eq 'OK') { $script:exeIn.Text = $f.FileName }
    })
    $script:dlg.FindName('cancelBtn').Add_Click({ $script:dlg.DialogResult = $false })
    $script:dlg.FindName('createBtn').Add_Click({
        $label = $script:labelIn.Text.Trim()
        $exe = $script:exeIn.Text.Trim()
        if (-not $label) { Fail 'חובה להזין שם לפריט.'; return }
        if (-not ($exe -match '(?i)\.exe$') -or -not (Test-Path -LiteralPath $exe -PathType Leaf)) { Fail 'בחר קובץ exe קיים.'; return }
        $relative = [string]$script:scopeIn.SelectedItem.Tag
        $verbName = 'PrsfCM_' + [Guid]::NewGuid().ToString('N')
        $parent = "HKEY_CURRENT_USER\Software\Classes\$relative\shell"
        $newKey = "$parent\$verbName"
        $cmd = '"' + $exe + '"'
        if ($script:passIn.IsChecked) { $cmd += $(if ($relative -eq 'Directory\Background') { ' "%V"' } else { ' "%1"' }) }
        try {
            if (Get-RegKey ('Registry::' + $parent)) { [void](Save-Backup $parent) }
            else {
                $p = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey("Software\Classes\$relative\shell")
                if (-not $p) { throw 'לא ניתן ליצור תיקיית פקודות.' }
                $p.Close()
            }
            $k = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey("Software\Classes\$relative\shell\$verbName")
            if (-not $k) { throw 'לא ניתן ליצור ערך Registry.' }
            $k.SetValue('MUIVerb',$label,[Microsoft.Win32.RegistryValueKind]::String)
            $k.SetValue('Icon',$exe,[Microsoft.Win32.RegistryValueKind]::String)
            $k.CreateSubKey('command').SetValue('',$cmd,[Microsoft.Win32.RegistryValueKind]::String)
            $k.Close()
            $log = "$newKey`r`n"; Add-Content -Path (Join-Path $script:AppDir 'added-keys.txt') -Value $log -Encoding UTF8
            $script:dlg.DialogResult = $true
            Reload-Entries
            Notify-Result 'הפקודה נוספה. אם היא לא מופיעה מיד בתפריט, סגור ופתח את סייר Windows.'
        } catch { Fail "נכשלה הוספה: $($_.Exception.Message)" }
    })
    [void]$script:dlg.ShowDialog()
}
function Delete-OwnEntry {
    $e = $script:entriesGrid.SelectedItem
    if (-not $e -or -not $e.IsOwn -or $e.Source -ne 'משתמש נוכחי') { return }
    if ([System.Windows.MessageBox]::Show("למחוק את הפקודה '$($e.Name)' שהוספת?`nלא יימחק שום קובץ תוכנה. יישמר גיבוי Registry.",'אישור מחיקה','YesNo','Warning') -ne 'Yes') { return }
    try {
        [void](Save-Backup $e.RegistryPath)
        Remove-Item -LiteralPath ('Registry::' + $e.RegistryPath) -Recurse -Force -ErrorAction Stop
        Reload-Entries
        Notify-Result 'הפקודה שהוספת נמחקה מהתפריט. קובץ התוכנה עצמו לא נמחק.'
    } catch { Fail "מחיקה נכשלה: $($_.Exception.Message)" }
}

$script:entriesGrid.Add_SelectionChanged({ Update-Detail })
$script:searchBox.Add_TextChanged({ $script:Search = $script:searchBox.Text.Trim(); Show-Entries })
$script:allBtn.Add_Click({ $script:Category='all'; Show-Entries })
$script:desktopBtn.Add_Click({ $script:Category='desktop'; Show-Entries })
$script:foldersBtn.Add_Click({ $script:Category='folders'; Show-Entries })
$script:filesBtn.Add_Click({ $script:Category='files'; Show-Entries })
$script:drivesBtn.Add_Click({ $script:Category='drives'; Show-Entries })
$script:refreshBtn.Add_Click({ Reload-Entries })
$script:backupBtn.Add_Click({ Start-Process explorer.exe -ArgumentList ('"' + $script:BackupDir + '"') })
$script:adminBtn.Add_Click({
    if (-not $script:ScriptFile) { Fail 'לא ניתן לזהות את נתיב הקובץ.'; return }
    try {
        $arg = '-NoProfile -ExecutionPolicy Bypass -STA -File "' + $script:ScriptFile + '"'
        Start-Process -FilePath 'powershell.exe' -ArgumentList $arg -Verb RunAs -ErrorAction Stop
        $script:Window.Close()
    } catch { Fail "לא הופעל כמנהל: $($_.Exception.Message)" }
})
$script:toggleBtn.Add_Click({ Perform-Toggle })
$script:addBtn.Add_Click({ Open-AddDialog })
$script:deleteOwnBtn.Add_Click({ Delete-OwnEntry })
Reload-Entries
[void]$script:Window.ShowDialog()
