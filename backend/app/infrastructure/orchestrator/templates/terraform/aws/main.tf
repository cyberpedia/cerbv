# Cerberus CTF - AWS Terraform Module
# Provisions EC2 instances for cloud exploitation challenges

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Variables
variable "instance_id" {
  description = "Unique challenge instance ID"
  type        = string
}

variable "user_id" {
  description = "User ID who owns this instance"
  type        = string
}

variable "team_id" {
  description = "Team ID (optional)"
  type        = string
  default     = ""
}

variable "canary_token" {
  description = "Canary token for anti-cheat"
  type        = string
  default     = ""
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "ami" {
  description = "AMI ID (defaults to latest Ubuntu 22.04)"
  type        = string
  default     = ""
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "challenge_port" {
  description = "Port the challenge service runs on"
  type        = number
  default     = 80
}

# Data sources
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Locals
locals {
  ami_id = var.ami != "" ? var.ami : data.aws_ami.ubuntu.id
  tags = {
    Name        = "cerberus-challenge-${var.instance_id}"
    UserId      = var.user_id
    TeamId      = var.team_id
    CanaryToken = var.canary_token
    ManagedBy   = "cerberus"
    InstanceId  = var.instance_id
  }
}

# VPC and Networking
resource "aws_vpc" "challenge" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = local.tags
}

resource "aws_internet_gateway" "challenge" {
  vpc_id = aws_vpc.challenge.id

  tags = local.tags
}

resource "aws_subnet" "challenge" {
  vpc_id                  = aws_vpc.challenge.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "${var.region}a"

  tags = local.tags
}

resource "aws_route_table" "challenge" {
  vpc_id = aws_vpc.challenge.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.challenge.id
  }

  tags = local.tags
}

resource "aws_route_table_association" "challenge" {
  subnet_id      = aws_subnet.challenge.id
  route_table_id = aws_route_table.challenge.id
}

# Security Group
resource "aws_security_group" "challenge" {
  name_prefix = "cerberus-challenge-${var.instance_id}"
  vpc_id      = aws_vpc.challenge.id
  description = "Security group for challenge instance ${var.instance_id}"

  # Allow challenge port from anywhere
  ingress {
    from_port   = var.challenge_port
    to_port     = var.challenge_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Challenge service port"
  }

  # Allow SSH from specific IP (for management)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"] # Restrict to internal
    description = "SSH access"
  }

  # Allow all outbound
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags

  lifecycle {
    create_before_destroy = true
  }
}

# IAM Role for instance
resource "aws_iam_role" "challenge" {
  name = "cerberus-challenge-${var.instance_id}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy" "challenge" {
  name = "cerberus-challenge-policy-${var.instance_id}"
  role = aws_iam_role.challenge.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::cerberus-challenge-files",
          "arn:aws:s3:::cerberus-challenge-files/*"
        ]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "challenge" {
  name = "cerberus-challenge-${var.instance_id}"
  role = aws_iam_role.challenge.name

  tags = local.tags
}

# EC2 Instance
resource "aws_instance" "challenge" {
  ami                    = local.ami_id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.challenge.id
  vpc_security_group_ids = [aws_security_group.challenge.id]
  iam_instance_profile   = aws_iam_instance_profile.challenge.name

  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  user_data = <<-EOF
              #!/bin/bash
              set -e
              
              # Update system
              apt-get update
              apt-get install -y docker.io docker-compose
              
              # Add canary token
              echo "CERBERUS_CANARY=${var.canary_token}" >> /etc/environment
              
              # Pull and run challenge container
              docker pull cerberus/challenge:${var.instance_id}
              docker run -d \
                -p ${var.challenge_port}:${var.challenge_port} \
                -e CERBERUS_CANARY=${var.canary_token} \
                --name challenge \
                cerberus/challenge:${var.instance_id}
              
              # Setup auto-termination after 2 hours
              echo "shutdown -h +120" | at now
              
              # Signal success
              echo "Challenge instance ready" > /var/log/challenge-setup.log
              EOF

  tags = local.tags
}

# Elastic IP (optional, for persistent IP)
resource "aws_eip" "challenge" {
  instance = aws_instance.challenge.id
  domain   = "vpc"

  tags = local.tags

  depends_on = [aws_internet_gateway.challenge]
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "challenge" {
  name              = "/cerberus/challenge/${var.instance_id}"
  retention_in_days = 1

  tags = local.tags
}

# Outputs
output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.challenge.id
}

output "public_ip" {
  description = "Public IP address"
  value       = aws_eip.challenge.public_ip
}

output "private_ip" {
  description = "Private IP address"
  value       = aws_instance.challenge.private_ip
}

output "access_url" {
  description = "URL to access the challenge"
  value       = "http://${aws_eip.challenge.public_ip}:${var.challenge_port}"
}

output "connection_string" {
  description = "SSH connection string"
  value       = "ssh ubuntu@${aws_eip.challenge.public_ip}"
}

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.challenge.id
}

output "security_group_id" {
  description = "Security Group ID"
  value       = aws_security_group.challenge.id
}