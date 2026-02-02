"""
Terraform Sandbox - Cloud-based challenge provisioning

Supports:
- AWS (EC2, ECS, Lambda)
- GCP (Compute Engine, Cloud Run)
- Azure (Virtual Machines, Container Instances)

Features:
- Terraform state management
- Auto-cleanup with TTL
- Cost tracking
- Multi-region support
"""

import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog

from ..models import (
    ChallengeInstance,
    InstanceStatus,
    NetworkConfig,
    ResourceLimits,
    SandboxType,
    SecurityProfile,
    SpawnResult,
)

logger = structlog.get_logger(__name__)


class TerraformSandbox:
    """
    Terraform-based cloud sandbox for cloud exploitation challenges.
    
    Provisions and manages cloud infrastructure using Terraform.
    """
    
    TERRAFORM_DIR = Path("/opt/cerberus/orchestrator/terraform")
    STATE_DIR = Path("/opt/cerberus/orchestrator/terraform-state")
    
    def __init__(
        self,
        provider: str = "aws",
        terraform_dir: Optional[Path] = None,
        state_dir: Optional[Path] = None,
    ):
        self.provider = provider
        self.terraform_dir = terraform_dir or self.TERRAFORM_DIR
        self.state_dir = state_dir or self.STATE_DIR
        
        # Provider-specific settings
        self._provider_config = self._load_provider_config()
        
        # Track deployments
        self._deployments: Dict[UUID, Dict[str, Any]] = {}
    
    def _load_provider_config(self) -> Dict[str, Any]:
        """Load provider-specific configuration."""
        configs = {
            "aws": {
                "region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
                "access_key": os.getenv("AWS_ACCESS_KEY_ID"),
                "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
            },
            "gcp": {
                "project": os.getenv("GCP_PROJECT_ID"),
                "region": os.getenv("GCP_REGION", "us-central1"),
                "credentials": os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
            },
            "azure": {
                "subscription_id": os.getenv("AZURE_SUBSCRIPTION_ID"),
                "client_id": os.getenv("AZURE_CLIENT_ID"),
                "client_secret": os.getenv("AZURE_CLIENT_SECRET"),
                "tenant_id": os.getenv("AZURE_TENANT_ID"),
            },
        }
        return configs.get(self.provider, {})
    
    async def spawn(self, instance: ChallengeInstance) -> SpawnResult:
        """
        Spawn cloud infrastructure using Terraform.
        
        Args:
            instance: Challenge instance configuration
            
        Returns:
            SpawnResult with infrastructure details
        """
        try:
            # Prepare Terraform workspace
            workspace_dir = await self._prepare_workspace(instance)
            
            # Generate Terraform configuration
            tf_config = await self._generate_terraform_config(instance)
            
            # Write configuration files
            await self._write_config_files(workspace_dir, tf_config)
            
            # Initialize Terraform
            await self._terraform_init(workspace_dir)
            
            # Apply Terraform
            outputs = await self._terraform_apply(workspace_dir, instance)
            
            # Update instance with outputs
            instance.provider_instance_id = outputs.get("instance_id")
            instance.network = NetworkConfig(
                external_ip=outputs.get("public_ip"),
                internal_ip=outputs.get("private_ip"),
            )
            instance.access_url = outputs.get("access_url")
            instance.connection_string = outputs.get("connection_string")
            
            # Track deployment
            self._deployments[instance.id] = {
                "workspace_dir": workspace_dir,
                "outputs": outputs,
            }
            
            logger.info(
                "Cloud infrastructure provisioned",
                instance_id=str(instance.id),
                provider=self.provider,
                instance_id=instance.provider_instance_id,
            )
            
            return SpawnResult(success=True, instance=instance)
            
        except Exception as e:
            logger.exception(
                "Failed to provision cloud infrastructure",
                instance_id=str(instance.id),
                provider=self.provider,
                error=str(e),
            )
            # Cleanup on failure
            await self._cleanup_workspace(instance)
            return SpawnResult(
                success=False,
                error_message=f"Terraform spawn failed: {str(e)}",
                retryable=False,
            )
    
    async def destroy(self, instance: ChallengeInstance) -> bool:
        """
        Destroy cloud infrastructure.
        
        Args:
            instance: Challenge instance to destroy
            
        Returns:
            True if destroyed successfully
        """
        try:
            deployment = self._deployments.get(instance.id)
            
            if not deployment:
                logger.warning(
                    "No deployment found for instance",
                    instance_id=str(instance.id),
                )
                return True
            
            workspace_dir = deployment["workspace_dir"]
            
            # Run terraform destroy
            await self._terraform_destroy(workspace_dir)
            
            # Cleanup workspace
            await self._cleanup_workspace(instance)
            
            # Remove from tracking
            if instance.id in self._deployments:
                del self._deployments[instance.id]
            
            logger.info(
                "Cloud infrastructure destroyed",
                instance_id=str(instance.id),
                provider=self.provider,
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to destroy cloud infrastructure",
                instance_id=str(instance.id),
                error=str(e),
            )
            return False
    
    async def exists(self, instance: ChallengeInstance) -> bool:
        """Check if cloud infrastructure still exists."""
        try:
            deployment = self._deployments.get(instance.id)
            if not deployment:
                return False
            
            workspace_dir = deployment["workspace_dir"]
            
            # Run terraform state list
            result = await self._run_terraform_command(
                workspace_dir,
                ["state", "list"],
            )
            
            return len(result.stdout.strip()) > 0
            
        except Exception:
            return False
    
    async def get_outputs(self, instance: ChallengeInstance) -> Dict[str, Any]:
        """Get Terraform outputs for the instance."""
        try:
            deployment = self._deployments.get(instance.id)
            if not deployment:
                return {}
            
            workspace_dir = deployment["workspace_dir"]
            
            result = await self._run_terraform_command(
                workspace_dir,
                ["output", "-json"],
            )
            
            return json.loads(result.stdout)
            
        except Exception as e:
            logger.error(
                "Failed to get Terraform outputs",
                instance_id=str(instance.id),
                error=str(e),
            )
            return {}
    
    async def _prepare_workspace(self, instance: ChallengeInstance) -> Path:
        """Prepare Terraform workspace for the instance."""
        workspace_name = f"{self.provider}-{instance.id}"
        workspace_dir = self.state_dir / workspace_name
        workspace_dir.mkdir(parents=True, exist_ok=True)
        return workspace_dir
    
    async def _cleanup_workspace(self, instance: ChallengeInstance) -> None:
        """Cleanup Terraform workspace."""
        try:
            workspace_name = f"{self.provider}-{instance.id}"
            workspace_dir = self.state_dir / workspace_name
            
            if workspace_dir.exists():
                import shutil
                shutil.rmtree(workspace_dir, ignore_errors=True)
                
        except Exception as e:
            logger.error(
                "Failed to cleanup workspace",
                instance_id=str(instance.id),
                error=str(e),
            )
    
    async def _generate_terraform_config(
        self,
        instance: ChallengeInstance,
    ) -> Dict[str, Any]:
        """Generate Terraform configuration for the instance."""
        # Get challenge-specific configuration
        module_name = instance.provider_metadata.get("terraform_module", "default")
        module_vars = instance.provider_metadata.get("module_vars", {})
        
        # Get template module
        module_path = self.terraform_dir / self.provider / module_name
        
        config = {
            "module": {
                "challenge": {
                    "source": str(module_path),
                    "instance_id": str(instance.id),
                    "user_id": str(instance.user_id),
                    "team_id": str(instance.team_id) if instance.team_id else "",
                    "canary_token": instance.canary_token or "",
                    **module_vars,
                }
            }
        }
        
        # Add provider configuration
        config["terraform"] = {
            "required_providers": {
                self.provider: {
                    "source": f"hashicorp/{self.provider}",
                }
            }
        }
        
        config["provider"] = {
            self.provider: self._provider_config
        }
        
        return config
    
    async def _write_config_files(
        self,
        workspace_dir: Path,
        config: Dict[str, Any],
    ) -> None:
        """Write Terraform configuration files."""
        # Write main.tf.json
        main_tf = workspace_dir / "main.tf.json"
        main_tf.write_text(json.dumps(config, indent=2))
        
        # Write backend configuration for state
        backend_config = {
            "terraform": {
                "backend": {
                    "local": {
                        "path": str(workspace_dir / "terraform.tfstate")
                    }
                }
            }
        }
        
        backend_tf = workspace_dir / "backend.tf.json"
        backend_tf.write_text(json.dumps(backend_config, indent=2))
    
    async def _terraform_init(self, workspace_dir: Path) -> None:
        """Initialize Terraform."""
        result = await self._run_terraform_command(
            workspace_dir,
            ["init", "-input=false"],
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Terraform init failed: {result.stderr}")
    
    async def _terraform_apply(
        self,
        workspace_dir: Path,
        instance: ChallengeInstance,
    ) -> Dict[str, Any]:
        """Apply Terraform configuration."""
        result = await self._run_terraform_command(
            workspace_dir,
            [
                "apply",
                "-input=false",
                "-auto-approve",
                f"-var=instance_id={instance.id}",
            ],
            timeout=300,  # 5 minute timeout
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Terraform apply failed: {result.stderr}")
        
        # Get outputs
        outputs_result = await self._run_terraform_command(
            workspace_dir,
            ["output", "-json"],
        )
        
        outputs = json.loads(outputs_result.stdout)
        
        # Flatten outputs
        flattened = {}
        for key, value in outputs.items():
            if isinstance(value, dict) and "value" in value:
                flattened[key] = value["value"]
            else:
                flattened[key] = value
        
        return flattened
    
    async def _terraform_destroy(self, workspace_dir: Path) -> None:
        """Destroy Terraform infrastructure."""
        result = await self._run_terraform_command(
            workspace_dir,
            ["destroy", "-input=false", "-auto-approve"],
            timeout=300,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Terraform destroy failed: {result.stderr}")
    
    async def _run_terraform_command(
        self,
        cwd: Path,
        args: List[str],
        timeout: int = 60,
    ) -> subprocess.CompletedProcess:
        """Run a Terraform command."""
        cmd = ["terraform"] + args
        
        logger.debug(
            "Running Terraform command",
            command=" ".join(cmd),
            cwd=str(cwd),
        )
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
            
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode,
                stdout=stdout.decode(),
                stderr=stderr.decode(),
            )
            
        except asyncio.TimeoutError:
            process.kill()
            raise TimeoutError(f"Terraform command timed out after {timeout}s")


# Pre-built Terraform modules for common challenge types
AWS_EC2_MODULE = '''
variable "instance_id" {}
variable "user_id" {}
variable "team_id" { default = "" }
variable "canary_token" { default = "" }
variable "instance_type" { default = "t3.micro" }
variable "ami" { default = "ami-0c55b159cbfafe1f0" }  # Ubuntu 22.04

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

resource "aws_instance" "challenge" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = var.instance_type

  tags = {
    Name        = "cerberus-challenge-${var.instance_id}"
    UserId      = var.user_id
    TeamId      = var.team_id
    CanaryToken = var.canary_token
    ManagedBy   = "cerberus"
  }

  user_data = <<-EOF
              #!/bin/bash
              echo "CERBERUS_CANARY=${var.canary_token}" >> /etc/environment
              # Additional setup here
              EOF
}

output "instance_id" {
  value = aws_instance.challenge.id
}

output "public_ip" {
  value = aws_instance.challenge.public_ip
}

output "private_ip" {
  value = aws_instance.challenge.private_ip
}

output "access_url" {
  value = "http://${aws_instance.challenge.public_ip}"
}

output "connection_string" {
  value = "ssh -i ~/.ssh/cerberus ubuntu@${aws_instance.challenge.public_ip}"
}
'''

GCP_COMPUTE_MODULE = '''
variable "instance_id" {}
variable "user_id" {}
variable "team_id" { default = "" }
variable "canary_token" { default = "" }
variable "machine_type" { default = "e2-micro" }
variable "zone" { default = "us-central1-a" }

resource "google_compute_instance" "challenge" {
  name         = "cerberus-challenge-${var.instance_id}"
  machine_type = var.machine_type
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
    }
  }

  network_interface {
    network = "default"
    access_config {}
  }

  metadata = {
    canary-token = var.canary_token
    user-id      = var.user_id
    team-id      = var.team_id
  }

  labels = {
    managed_by = "cerberus"
  }
}

output "instance_id" {
  value = google_compute_instance.challenge.id
}

output "public_ip" {
  value = google_compute_instance.challenge.network_interface[0].access_config[0].nat_ip
}

output "private_ip" {
  value = google_compute_instance.challenge.network_interface[0].network_ip
}

output "access_url" {
  value = "http://${google_compute_instance.challenge.network_interface[0].access_config[0].nat_ip}"
}
'''


def create_default_modules(base_dir: Path) -> None:
    """Create default Terraform modules."""
    # AWS modules
    aws_dir = base_dir / "aws"
    aws_dir.mkdir(parents=True, exist_ok=True)
    
    (aws_dir / "ec2" / "main.tf").parent.mkdir(parents=True, exist_ok=True)
    (aws_dir / "ec2" / "main.tf").write_text(AWS_EC2_MODULE)
    
    # GCP modules
    gcp_dir = base_dir / "gcp"
    gcp_dir.mkdir(parents=True, exist_ok=True)
    
    (gcp_dir / "compute" / "main.tf").parent.mkdir(parents=True, exist_ok=True)
    (gcp_dir / "compute" / "main.tf").write_text(GCP_COMPUTE_MODULE)