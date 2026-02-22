# CoDRAG Team Sync — AWS ECS Reference

For enterprise teams deploying inside a VPC. The `codrag/headless:gpu` image runs on AWS ECS with GPU support.

## Architecture

```
CodeCommit / GitHub → EventBridge → ECS RunTask → S3 (internal bucket)
                                                      ↓
                                          Developer CoDRAG clients
```

## Setup

1. **Create an ECR repository** or pull from GHCR:
   ```bash
   docker pull ghcr.io/ericbintner/codrag-headless:gpu
   docker tag ghcr.io/ericbintner/codrag-headless:gpu \
     YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/codrag-headless:gpu
   docker push YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/codrag-headless:gpu
   ```

2. **Create an S3 bucket** for index storage (private, no public access).

3. **Create IAM roles:**
   - `ecsTaskExecutionRole` — Standard ECS execution role.
   - `codragHeadlessRole` — Task role with `s3:GetObject`, `s3:PutObject`, `s3:ListBucket` on your bucket.

4. **Register the task definition:**
   ```bash
   aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json
   ```

5. **Trigger via EventBridge** on CodeCommit pushes or GitHub webhooks.

## Notes

- **No static S3 keys needed:** The task role provides temporary credentials via IAM.
- **GPU instances:** Use `p3.2xlarge` (V100) or `g4dn.xlarge` (T4) EC2 instances in your ECS cluster.
- **Azure equivalent:** Use Azure Container Apps with GPU profiles and Azure Blob storage.
