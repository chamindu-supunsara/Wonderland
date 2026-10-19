. "$PSScriptRoot\aws-common.ps1"
Assert-ProjectPython
foreach ($EventService in @('catalog','booking','analytics')) {
  Push-Location (Join-Path $ProjectRoot "services\$EventService")
  try {
    Write-Host $EventService
    switch ($EventService) {
      'catalog' { & $ProjectPython -m app.event_worker status }
      'booking' { & $ProjectPython -m booking_app.event_worker status }
      'analytics' { & $ProjectPython -m analytics_app.worker --status }
    }
    Assert-NativeSuccess 'Reading event persistence'
  } finally { Pop-Location }
}
$EventOutputs = Get-Content -Raw (Join-Path $ProjectRoot '.local\events.json') | ConvertFrom-Json
foreach ($EventQueueKey in @('BookingPricesUrl','AnalyticsBookingsUrl','PaymentBookingsUrl',
  'BookingPricesDLQUrl','AnalyticsBookingsDLQUrl','PaymentBookingsDLQUrl','DeliveryDLQUrl')) {
  Write-Host $EventQueueKey
  & $LocalAws sqs get-queue-attributes --queue-url $EventOutputs.$EventQueueKey --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible --profile wonderland-dev --region ap-south-1 --no-cli-pager
  Assert-NativeSuccess 'Reading queue depth'
}
