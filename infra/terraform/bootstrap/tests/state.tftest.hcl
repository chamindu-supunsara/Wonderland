mock_provider "aws" {}
run "protected_state" {
  command = plan
  assert {
    condition     = !aws_s3_bucket.state.force_destroy && aws_s3_bucket_public_access_block.state.block_public_acls && aws_s3_bucket_public_access_block.state.block_public_policy && aws_s3_bucket_public_access_block.state.restrict_public_buckets && aws_s3_bucket_public_access_block.state.ignore_public_acls
    error_message = "State bucket must reject public access and automatic object deletion."
  }
  assert {
    condition     = aws_s3_bucket_versioning.state.versioning_configuration[0].status == "Enabled"
    error_message = "State versions must be retained."
  }
}
