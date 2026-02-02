"""
Cerberus Admin CLI - cerberusctl
Python Click-based admin tool for Cerberus CTF Platform management.
"""

import click
import json
import time
from datetime import datetime
from typing import Optional
import requests


# ============================================
# CLI Configuration
# ============================================

class Context:
    """CLI context for global settings."""
    
    def __init__(self):
        self.api_url: str = "http://localhost:8000"
        self.api_key: Optional[str] = None
        self.output_format: str = "table"
        self.quiet: bool = False


pass_context = click.make_pass_decorator(Context, ensure=True)


def setup_api_client(ctx: Context) -> requests.Session:
    """Create API client with auth headers."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    if ctx.api_key:
        session.headers.update({"Authorization": f"Bearer {ctx.api_key}"})
    return session


# ============================================
# Base Commands
# ============================================

@click.group()
@click.option(
    "--api-url",
    default="http://localhost:8000",
    help="API URL for Cerberus server",
    envvar="CERBERUS_API_URL",
)
@click.option(
    "--api-key",
    help="API key for authentication",
    envvar="CERBERUS_API_KEY",
)
@click.option(
    "--output",
    type=click.Choice(["table", "json", "yaml"]),
    default="table",
    help="Output format",
)
@click.option(
    "--quiet",
    is_flag=True,
    help="Suppress output except errors",
)
@click.pass_context
def cli(
    ctx: click.Context,
    api_url: str,
    api_key: Optional[str],
    output: str,
    quiet: bool,
):
    """Cerberus CTF Platform Admin CLI"""
    ctx.ensure_object(Context)
    ctx.obj.api_url = api_url
    ctx.obj.api_key = api_key
    ctx.obj.output_format = output
    ctx.obj.quiet = quiet


# ============================================
# User Management Commands
# ============================================

@cli.group()
def user():
    """User management commands"""
    pass


@user.command("list")
@click.option("--team-id", help="Filter by team ID")
@click.option("--active/--inactive", default=True)
@pass_context
def user_list(ctx: Context, team_id: Optional[str], active: bool):
    """List all users"""
    session = setup_api_client(ctx)
    params = {"active": active}
    if team_id:
        params["team_id"] = team_id
    
    try:
        response = session.get(f"{ctx.api_url}/api/v1/users/", params=params)
        response.raise_for_status()
        users = response.json()
        
        if ctx.obj.output_format == "json":
            click.echo(json.dumps(users, indent=2))
        else:
            click.echo(f"{'ID':<40} {'Username':<20} {'Team':<10} {'Active'}")
            click.echo("-" * 80)
            for user in users:
                click.echo(
                    f"{user.get('id', '')[:40]:<40} "
                    f"{user.get('username', ''):<20} "
                    f"{user.get('team_id', '')[:10] if user.get('team_id') else 'N/A':<10} "
                    f"{'Yes' if user.get('is_active') else 'No'}"
                )
    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)


@user.command("create")
@click.argument("username")
@click.argument("email")
@click.option("--team-id", help="Team ID to assign")
@click.option("--admin", is_flag=True, help="Make user an admin")
@pass_context
def user_create(ctx: Context, username: str, email: str, team_id: Optional[str], admin: bool):
    """Create a new user"""
    session = setup_api_client(ctx)
    data = {
        "username": username,
        "email": email,
        "team_id": team_id,
        "is_admin": admin,
    }
    
    try:
        response = session.post(f"{ctx.api_url}/api/v1/users/", json=data)
        response.raise_for_status()
        user = response.json()
        
        if not ctx.quiet:
            click.echo(f"User created: {user.get('id')}")
            if ctx.obj.output_format == "json":
                click.echo(json.dumps(user, indent=2))
    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)


@user.command("delete")
@click.argument("user_id")
@click.option("--force", is_flag=True, help="Skip confirmation")
@pass_context
def user_delete(ctx: Context, user_id: str, force: bool):
    """Delete a user"""
    if not force:
        if not click.confirm(f"Delete user {user_id}?"):
            return
    
    session = setup_api_client(ctx)
    
    try:
        response = session.delete(f"{ctx.api_url}/api/v1/users/{user_id}")
        response.raise_for_status()
        
        if not ctx.quiet:
            click.echo(f"User {user_id} deleted")
    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)


@user.command("export")
@click.argument("user_id")
@pass_context
def user_export(ctx: Context, user_id: str):
    """Export user data (GDPR)"""
    session = setup_api_client(ctx)
    
    try:
        response = session.post(f"{ctx.api_url}/api/v1/privacy/user/request-export")
        response.raise_for_status()
        result = response.json()
        
        if ctx.obj.output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Export requested: {result.get('request_id')}")
            click.echo(f"Status: {result.get('status')}")
    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)


# ============================================
# Challenge Management Commands
# ============================================

@cli.group()
def challenge():
    """Challenge management commands"""
    pass


@challenge.command("list")
@click.option("--category", help="Filter by category")
@click.option("--active/--inactive", default=True)
@pass_context
def challenge_list(ctx: Context, category: Optional[str], active: bool):
    """List all challenges"""
    session = setup_api_client(ctx)
    params = {"active": active}
    if category:
        params["category"] = category
    
    try:
        response = session.get(f"{ctx.api_url}/api/v1/challenges/", params=params)
        response.raise_for_status()
        challenges = response.json()
        
        if ctx.obj.output_format == "json":
            click.echo(json.dumps(challenges, indent=2))
        else:
            click.echo(f"{'ID':<40} {'Name':<30} {'Category':<15} {'Points':<10}")
            click.echo("-" * 95)
            for ch in challenges:
                click.echo(
                    f"{ch.get('id', '')[:40]:<40} "
                    f"{ch.get('name', ''):<30} "
                    f"{ch.get('category', ''):<15} "
                    f"{ch.get('points', 0)}"
                )
    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)


@challenge.command("deploy")
@click.argument("challenge_id")
@click.option("--force", is_flag=True, help="Redeploy if already active")
@pass_context
def challenge_deploy(ctx: Context, challenge_id: str, force: bool):
    """Deploy a challenge sandbox"""
    session = setup_api_client(ctx)
    data = {"force": force}
    
    try:
        response = session.post(
            f"{ctx.api_url}/api/v1/orchestrator/challenges/{challenge_id}/deploy",
            json=data
        )
        response.raise_for_status()
        result = response.json()
        
        if ctx.obj.output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Challenge {challenge_id} deployment started")
            click.echo(f"Instance ID: {result.get('instance_id')}")
    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)


@challenge.command("destroy")
@click.argument("challenge_id")
@click.option("--force", is_flag=True, help="Skip confirmation")
@pass_context
def challenge_destroy(ctx: Context, challenge_id: str, force: bool):
    """Destroy a challenge sandbox"""
    if not force:
        if not click.confirm(f"Destroy challenge {challenge_id}?"):
            return
    
    session = setup_api_client(ctx)
    
    try:
        response = session.post(
            f"{ctx.api_url}/api/v1/orchestrator/challenges/{challenge_id}/destroy"
        )
        response.raise_for_status()
        
        if not ctx.quiet:
            click.echo(f"Challenge {challenge_id} destroyed")
    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)


@challenge.command("status")
@click.argument("challenge_id")
@pass_context
def challenge_status(ctx: Context, challenge_id: str):
    """Get challenge status"""
    session = setup_api_client(ctx)
    
    try:
        response = session.get(
            f"{ctx.api_url}/api/v1/orchestrator/challenges/{challenge_id}/status"
        )
        response.raise_for_status()
        status = response.json()
        
        if ctx.obj.output_format == "json":
            click.echo(json.dumps(status, indent=2))
        else:
            click.echo(f"Challenge: {status.get('name')}")
            click.echo(f"Status: {status.get('status')}")
            click.echo(f"Instances: {status.get('instance_count', 0)}")
    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)


# ============================================
# Backup Commands
# ============================================

@cli.group()
def backup():
    """Backup management commands"""
    pass


@backup.command("create")
@click.option("--type", type=click.Choice(["full", "diff", "archive"]), default="full")
@pass_context
def backup_create(ctx: Context, type: str):
    """Create a backup"""
    session = setup_api_client(ctx)
    data = {"type": type}
    
    try:
        response = session.post(f"{ctx.api_url}/api/v1/admin/backup/create", json=data)
        response.raise_for_status()
        result = response.json()
        
        if ctx.obj.output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Backup started: {result.get('backup_id')}")
            click.echo(f"Type: {result.get('type')}")
    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)


@backup.command("list")
@pass_context
def backup_list(ctx: Context):
    """List available backups"""
    session = setup_api_client(ctx)
    
    try:
        response = session.get(f"{ctx.api_url}/api/v1/admin/backup/list")
        response.raise_for_status()
        backups = response.json()
        
        if ctx.obj.output_format == "json":
            click.echo(json.dumps(backups, indent=2))
        else:
            click.echo(f"{'ID':<40} {'Type':<10} {'Size':<15} {'Created'}")
            click.echo("-" * 85)
            for backup in backups:
                click.echo(
                    f"{backup.get('id', '')[:40]:<40} "
                    f"{backup.get('type', ''):<10} "
                    f"{backup.get('size_human', ''):<15} "
                    f"{backup.get('created_at', '')}"
                )
    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)


@backup.command("restore")
@click.argument("backup_id")
@click.option("--force", is_flag=True, help="Skip confirmation")
@pass_context
def backup_restore(ctx: Context, backup_id: str, force: bool):
    """Restore from backup"""
    if not force:
        if not click.confirm(f"Restore from backup {backup_id}?"):
            return
    
    session = setup_api_client(ctx)
    
    try:
        response = session.post(
            f"{ctx.api_url}/api/v1/admin/backup/restore",
            json={"backup_id": backup_id}
        )
        response.raise_for_status()
        result = response.json()
        
        if not ctx.quiet:
            click.echo(f"Restore started: {result.get('restore_id')}")
    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)


# ============================================
# System Commands
# ============================================

@cli.group()
def system():
    """System management commands"""
    pass


@system.command("health")
@click.option("--wait", is_flag=True, help="Wait for healthy status")
@pass_context
def system_health(ctx: Context, wait: bool):
    """Check system health"""
    session = setup_api_client(ctx)
    
    max_retries = 10 if wait else 1
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            response = session.get(f"{ctx.api_url}/health")
            response.raise_for_status()
            health = response.json()
            
            if ctx.obj.output_format == "json":
                click.echo(json.dumps(health, indent=2))
            else:
                status = health.get("status", "unknown")
                color = "green" if status == "healthy" else "red"
                click.secho(f"Status: {status}", fg=color)
                
                components = health.get("components", {})
                for name, comp in components.items():
                    comp_status = comp.get("status", "unknown")
                    comp_color = "green" if comp_status == "healthy" else "red"
                    click.secho(f"  {name}: {comp_status}", fg=comp_color)
            
            if health.get("status") == "healthy":
                return
                
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                click.echo(f"Error: {e}", err=True)


@system.command("stats")
@pass_context
def system_stats(ctx: Context):
    """Get system statistics"""
    session = setup_api_client(ctx)
    
    try:
        response = session.get(f"{ctx.api_url}/api/v1/admin/stats")
        response.raise_for_status()
        stats = response.json()
        
        if ctx.obj.output_format == "json":
            click.echo(json.dumps(stats, indent=2))
        else:
            click.echo("System Statistics")
            click.echo("=" * 40)
            for key, value in stats.items():
                if isinstance(value, dict):
                    click.echo(f"\n{key}:")
                    for k, v in value.items():
                        click.echo(f"  {k}: {v}")
                else:
                    click.echo(f"{key}: {value}")
    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)


@system.command("status")
@pass_context
def system_status(ctx: Context):
    """Get detailed system status"""
    session = setup_api_client(ctx)
    
    try:
        response = session.get(f"{ctx.api_url}/api/v1/admin/status")
        response.raise_for_status()
        status = response.json()
        
        if ctx.obj.output_format == "json":
            click.echo(json.dumps(status, indent=2))
        else:
            click.echo(f"Version: {status.get('version')}")
            click.echo(f"Uptime: {status.get('uptime')}")
            click.echo(f"Active Users: {status.get('active_users', 0)}")
            click.echo(f"Active Challenges: {status.get('active_challenges', 0)}")
            click.echo(f"Active Instances: {status.get('active_instances', 0)}")
    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)


# ============================================
# Privacy Commands
# ============================================

@cli.group()
def privacy():
    """Privacy and GDPR commands"""
    pass


@privacy.command("mode")
@click.argument("mode", type=click.Choice(["full", "anonymous", "stealth", "delayed"]))
@click.option("--delayed-minutes", default=15, help="Delay in minutes for delayed mode")
@pass_context
def privacy_mode(ctx: Context, mode: str, delayed_minutes: int):
    """Set privacy mode"""
    session = setup_api_client(ctx)
    data = {"mode": mode, "delayed_minutes": delayed_minutes}
    
    try:
        response = session.post(f"{ctx.api_url}/api/v1/privacy/mode", json=data)
        response.raise_for_status()
        result = response.json()
        
        if not ctx.quiet:
            click.echo(f"Privacy mode set to: {mode}")
    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)


@privacy.command("status")
@pass_context
def privacy_status(ctx: Context):
    """Get current privacy status"""
    session = setup_api_client(ctx)
    
    try:
        response = session.get(f"{ctx.api_url}/api/v1/privacy/status")
        response.raise_for_status()
        status = response.json()
        
        if ctx.obj.output_format == "json":
            click.echo(json.dumps(status, indent=2))
        else:
            click.echo(f"Mode: {status.get('mode')}")
            click.echo(f"Description: {status.get('mode_description')}")
            click.echo(f"Team names visible: {status.get('team_names_visible')}")
            click.echo(f"Solves visible: {status.get('solves_visible')}")
            click.echo(f"Timestamps visible: {status.get('timestamps_visible')}")
    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)


@privacy.command("retention")
@pass_context
def privacy_retention(ctx: Context):
    """Get retention policy status"""
    session = setup_api_client(ctx)
    
    try:
        response = session.get(f"{ctx.api_url}/api/v1/privacy/admin/retention/policies")
        response.raise_for_status()
        policies = response.json()
        
        if ctx.obj.output_format == "json":
            click.echo(json.dumps(policies, indent=2))
        else:
            click.echo("Retention Policies")
            click.echo("=" * 50)
            for policy in policies.get("policies", []):
                click.echo(f"\n{policy.get('data_type')}:")
                click.echo(f"  Retention: {policy.get('retention_days')} days")
                click.echo(f"  Anonymize after: {policy.get('anonymize_after')} days")
                click.echo(f"  Delete after: {policy.get('delete_after')} days")
    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)


# ============================================
# Main Entry Point
# ============================================

if __name__ == "__main__":
    cli()
