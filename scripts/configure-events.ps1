. "$PSScriptRoot\aws-common.ps1"
Push-Location $ProjectRoot
try {
    $EventStackJson = & $LocalAws cloudformation describe-stacks --stack-name wonderland-events-dev --profile wonderland-dev --region ap-south-1 --no-cli-pager --output json
    Assert-NativeSuccess 'Reading the event stack'
    $EventStack = ($EventStackJson | ConvertFrom-Json).Stacks[0]
    if ($EventStack.StackStatus -notin @('CREATE_COMPLETE','UPDATE_COMPLETE')) { throw "Stack is $($EventStack.StackStatus)" }
    $EventOutputs = @{}
    foreach ($EventOutput in $EventStack.Outputs) { $EventOutputs[$EventOutput.OutputKey] = $EventOutput.OutputValue }
    $EventOutputs | ConvertTo-Json | Set-Content -LiteralPath '.local\events.json'
    $EventAssumePolicy = @{
      Version = '2012-10-17'
      Statement = @(@{
        Effect = 'Allow'; Action = 'sts:AssumeRole'
        Resource = @($EventOutputs.CatalogPublisherRoleArn, $EventOutputs.BookingPublisherRoleArn,
          $EventOutputs.BookingConsumerRoleArn, $EventOutputs.AnalyticsConsumerRoleArn)
      })
    }
    $EventAssumePolicy | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath '.local\assume-worker-roles.json'
    $EventProfiles = @{
      'wonderland-catalog-publisher' = 'CatalogPublisherRoleArn'
      'wonderland-booking-publisher' = 'BookingPublisherRoleArn'
      'wonderland-booking-consumer' = 'BookingConsumerRoleArn'
      'wonderland-analytics-consumer' = 'AnalyticsConsumerRoleArn'
    }
    foreach ($EventProfile in $EventProfiles.GetEnumerator()) {
      & $LocalAws configure set role_arn $EventOutputs[$EventProfile.Value] --profile $EventProfile.Key
      Assert-NativeSuccess 'Configuring scoped role'
      & $LocalAws configure set source_profile wonderland-worker-source --profile $EventProfile.Key
      & $LocalAws configure set region ap-south-1 --profile $EventProfile.Key
    }
    Write-Host 'Saved public resource identifiers and four scoped-role profiles in ignored .local files.'
} finally { Pop-Location }

