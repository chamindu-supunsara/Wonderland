param(
  [Parameter(Mandatory)][ValidateSet('catalog-publish','booking-publish','booking-prices','analytics')]
  [string]$Worker,
  [switch]$Once
)
. "$PSScriptRoot\aws-common.ps1"
Assert-ProjectPython
$EventConfigPath = Join-Path $ProjectRoot '.local\events.json'
if (-not (Test-Path -LiteralPath $EventConfigPath)) { throw 'Run scripts\configure-events.ps1 first.' }
$EventConfig = Get-Content -Raw -LiteralPath $EventConfigPath | ConvertFrom-Json
switch ($Worker) {
  'catalog-publish' {
    $EventService = 'catalog'; $EventModule = 'app.event_worker'; $EventAction = @('publish')
    $env:EVENTS_TOPIC_ARN = $EventConfig.CatalogTopicArn; $env:AWS_PROFILE = 'wonderland-catalog-publisher'
  }
  'booking-publish' {
    $EventService = 'booking'; $EventModule = 'booking_app.event_worker'; $EventAction = @('publish')
    $env:EVENTS_TOPIC_ARN = $EventConfig.BookingTopicArn; $env:AWS_PROFILE = 'wonderland-booking-publisher'
  }
  'booking-prices' {
    $EventService = 'booking'; $EventModule = 'booking_app.event_worker'; $EventAction = @('consume-prices')
    $env:PRICING_QUEUE_URL = $EventConfig.BookingPricesUrl; $env:AWS_PROFILE = 'wonderland-booking-consumer'
  }
  'analytics' {
    $EventService = 'analytics'; $EventModule = 'analytics_app.worker'; $EventAction = @()
    $env:BOOKING_QUEUE_URL = $EventConfig.AnalyticsBookingsUrl; $env:AWS_PROFILE = 'wonderland-analytics-consumer'
  }
}
if ($Once) { $EventAction += '--once' }
Push-Location (Join-Path $ProjectRoot "services\$EventService")
try {
  & $ProjectPython -m $EventModule @EventAction
  Assert-NativeSuccess "Running $Worker"
} finally { Pop-Location }

